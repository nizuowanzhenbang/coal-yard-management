"""入场登记 API"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_write
from app.models.stock_in import StockIn
from app.models.yard import CoalYard, YardStatus
from app.models.user import User
from app.schemas.stock_in import StockInCreate, StockInUpdate, StockInResponse
from app.utils.helpers import api_response, paginate_response, generate_stockin_no
from app.utils.csv_export import stream_csv, fmt_dt
from app.utils.integration_client import (
    fetch_order_info, notify_order_received, fetch_order_quality,
)
from app.utils.coal_score import calc_score

router = APIRouter(prefix="/api/stock-in", tags=["入场登记"])


def _enrich(s: StockIn, with_score: bool = False) -> dict:
    result = StockInResponse.model_validate(s).model_dump()
    if s.yard:
        result["yard_code"] = s.yard.code
        result["yard_name"] = s.yard.name
    aging = (datetime.utcnow() - s.stocked_at).days
    if s.remaining_quantity > 0:
        result["aging_days"] = aging
    else:
        result["aging_days"] = None
    if with_score:
        score, breakdown = calc_score(
            s.calorific_value, s.ash, s.sulfur, s.moisture, aging,
        )
        result["score"] = score
        result["score_breakdown"] = breakdown
    return result


@router.get("")
def list_stockins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    yard_id: Optional[int] = None,
    coal_type: Optional[str] = None,
    order_no: Optional[str] = None,
    has_remaining: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(StockIn).options(joinedload(StockIn.yard))
    if yard_id:
        q = q.filter(StockIn.yard_id == yard_id)
    if coal_type:
        q = q.filter(StockIn.coal_type == coal_type)
    if order_no:
        q = q.filter(StockIn.order_no == order_no)
    if has_remaining is True:
        q = q.filter(StockIn.remaining_quantity > 0)
    elif has_remaining is False:
        q = q.filter(StockIn.remaining_quantity <= 0)

    total = q.count()
    rows = (
        q.order_by(StockIn.stocked_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_enrich(r) for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.get("/export")
def export_stockins(
    yard_id: Optional[int] = None,
    coal_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(StockIn).options(joinedload(StockIn.yard))
    if yard_id:
        q = q.filter(StockIn.yard_id == yard_id)
    if coal_type:
        q = q.filter(StockIn.coal_type == coal_type)
    rows = q.order_by(StockIn.stocked_at.desc()).all()
    headers = [
        "入场单号", "堆区", "煤种", "入场量(吨)", "剩余(吨)", "订单号", "供应商",
        "热值", "灰分", "硫分", "水分", "入场时间", "登记人",
    ]
    data = [
        [
            r.stockin_no, r.yard.name if r.yard else "", r.coal_type,
            r.quantity, r.remaining_quantity, r.order_no or "",
            r.supplier_name or "", r.calorific_value or "", r.ash or "",
            r.sulfur or "", r.moisture or "",
            fmt_dt(r.stocked_at), r.operator or "",
        ]
        for r in rows
    ]
    return stream_csv("入场记录", headers, data)


@router.post("")
def create_stockin(
    payload: StockInCreate, db: Session = Depends(get_db),
    current: User = Depends(require_write),
):
    yard = db.query(CoalYard).filter(CoalYard.id == payload.yard_id).first()
    if not yard:
        raise HTTPException(404, "堆区不存在")
    if yard.status != YardStatus.ACTIVE:
        raise HTTPException(400, f"堆区当前状态 {yard.status.value}，不可入场")
    if yard.designated_coal_type != payload.coal_type:
        raise HTTPException(400, f"堆区设计煤种为 {yard.designated_coal_type}，与入场煤种 {payload.coal_type} 不符")

    # 容量校验
    current_inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
        StockIn.yard_id == yard.id
    ).scalar() or 0
    remaining_capacity = yard.capacity - current_inv
    if payload.quantity > remaining_capacity:
        raise HTTPException(400, f"超出堆区剩余容量（剩 {remaining_capacity:.1f} 吨）")

    # 集成：如填了订单号，尝试拉煤质数据
    data = payload.model_dump()
    quality_synced = False
    if data.get("order_no"):
        # 拉订单基本信息（如未填供应商则补全）
        order_info = fetch_order_info(data["order_no"])
        if order_info:
            data.setdefault("supplier_name", order_info.get("supplier_name"))
            data["supplier_name"] = data.get("supplier_name") or order_info.get("supplier_name")
            if not data.get("contract_no"):
                data["contract_no"] = order_info.get("contract_no")
        # 拉化验数据（用户未手填时自动覆盖）
        quality = fetch_order_quality(data["order_no"])
        if quality:
            for k in ("calorific_value", "ash", "sulfur", "moisture"):
                if data.get(k) is None:
                    data[k] = quality.get(k)
            quality_synced = True

    next_seq = (db.query(func.count(StockIn.id)).scalar() or 0) + 1
    record = StockIn(
        stockin_no=generate_stockin_no(next_seq),
        operator=current.username,
        remaining_quantity=data["quantity"],
        quality_synced=quality_synced,
        **data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 异步通知 fuel-procurement（失败不阻塞）
    if record.order_no:
        notify_order_received(record.order_no, yard.code, record.quantity)

    return api_response(message="入场已登记", data=_enrich(record))


@router.get("/{stockin_id}")
def get_stockin(stockin_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(StockIn).options(joinedload(StockIn.yard)).filter(StockIn.id == stockin_id).first()
    if not s:
        raise HTTPException(404, "入场记录不存在")
    return api_response(data=_enrich(s, with_score=True))


@router.put("/{stockin_id}")
def update_stockin(
    stockin_id: int, payload: StockInUpdate,
    db: Session = Depends(get_db), _: User = Depends(require_write),
):
    s = db.query(StockIn).filter(StockIn.id == stockin_id).first()
    if not s:
        raise HTTPException(404, "入场记录不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return api_response(message="已更新", data=_enrich(s))


@router.post("/{stockin_id}/sync-quality")
def sync_quality(
    stockin_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_write),
):
    """从煤质化验系统重新拉化验数据"""
    s = db.query(StockIn).filter(StockIn.id == stockin_id).first()
    if not s:
        raise HTTPException(404, "入场记录不存在")
    if not s.order_no:
        raise HTTPException(400, "无关联订单号，无法同步")
    q = fetch_order_quality(s.order_no)
    if not q:
        raise HTTPException(503, "煤质化验系统未对接或无数据")
    for k in ("calorific_value", "ash", "sulfur", "moisture"):
        if q.get(k) is not None:
            setattr(s, k, q.get(k))
    s.quality_synced = True
    db.commit()
    db.refresh(s)
    return api_response(message="已同步化验数据", data=_enrich(s))
