"""堆区 API"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_write, require_approver
from app.config import settings
from app.models.yard import CoalYard, YardStatus
from app.models.stock_in import StockIn
from app.models.user import User
from app.schemas.yard import YardCreate, YardUpdate, YardResponse
from app.utils.helpers import api_response, paginate_response, generate_yard_code
from app.utils.csv_export import stream_csv, fmt_dt

router = APIRouter(prefix="/api/yards", tags=["煤场堆区"])


def _enrich_yard(db: Session, yard: CoalYard) -> dict:
    result = YardResponse.model_validate(yard).model_dump()
    inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
        StockIn.yard_id == yard.id
    ).scalar() or 0
    result["current_inventory"] = round(float(inv), 1)
    result["utilization"] = round(float(inv) / yard.capacity * 100, 1) if yard.capacity else 0
    # 最老批次库龄
    oldest = (
        db.query(StockIn)
        .filter(StockIn.yard_id == yard.id, StockIn.remaining_quantity > 0)
        .order_by(StockIn.stocked_at.asc())
        .first()
    )
    result["oldest_in_days"] = (datetime.utcnow() - oldest.stocked_at).days if oldest else None
    return result


@router.get("")
def list_yards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[YardStatus] = None,
    coal_type: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(CoalYard)
    if status:
        q = q.filter(CoalYard.status == status)
    if coal_type:
        q = q.filter(CoalYard.designated_coal_type == coal_type)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((CoalYard.name.like(like)) | (CoalYard.code.like(like)))

    total = q.count()
    rows = (
        q.order_by(CoalYard.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_enrich_yard(db, r) for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.get("/export")
def export_yards(
    status: Optional[YardStatus] = None,
    coal_type: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(CoalYard)
    if status:
        q = q.filter(CoalYard.status == status)
    if coal_type:
        q = q.filter(CoalYard.designated_coal_type == coal_type)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((CoalYard.name.like(like)) | (CoalYard.code.like(like)))
    rows = q.order_by(CoalYard.code).all()
    headers = ["编号", "名称", "设计煤种", "设计容量(吨)", "当前库存(吨)", "利用率(%)", "状态", "位置", "创建时间"]
    data = []
    for r in rows:
        d = _enrich_yard(db, r)
        data.append([
            r.code, r.name, r.designated_coal_type, r.capacity,
            d["current_inventory"], d["utilization"],
            r.status.value if r.status else "", r.location or "",
            fmt_dt(r.created_at),
        ])
    return stream_csv("煤场堆区列表", headers, data)


@router.post("")
def create_yard(
    payload: YardCreate, db: Session = Depends(get_db),
    _: User = Depends(require_write),
):
    if db.query(CoalYard).filter(CoalYard.name == payload.name).first():
        raise HTTPException(400, "堆区名称已存在")
    next_seq = (db.query(func.count(CoalYard.id)).scalar() or 0) + 1
    yard = CoalYard(
        code=generate_yard_code(next_seq),
        status=YardStatus.ACTIVE,
        **payload.model_dump(),
    )
    db.add(yard)
    db.commit()
    db.refresh(yard)
    return api_response(message="堆区已创建", data=_enrich_yard(db, yard))


@router.get("/{yard_id}")
def get_yard(yard_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    y = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not y:
        raise HTTPException(404, "堆区不存在")
    result = _enrich_yard(db, y)
    # 附库龄分布
    aging_warn = settings.AGING_WARN_DAYS
    aging_danger = settings.AGING_DANGER_DAYS
    now = datetime.utcnow()
    batches = (
        db.query(StockIn)
        .filter(StockIn.yard_id == y.id, StockIn.remaining_quantity > 0)
        .order_by(StockIn.stocked_at.asc())
        .all()
    )
    aging_summary = {"green": 0.0, "yellow": 0.0, "red": 0.0}
    for b in batches:
        days = (now - b.stocked_at).days
        bucket = "red" if days > aging_danger else "yellow" if days > aging_warn else "green"
        aging_summary[bucket] += b.remaining_quantity
    result["aging_summary"] = {k: round(v, 1) for k, v in aging_summary.items()}
    result["batch_count"] = len(batches)
    return api_response(data=result)


@router.put("/{yard_id}")
def update_yard(
    yard_id: int, payload: YardUpdate,
    db: Session = Depends(get_db), _: User = Depends(require_write),
):
    y = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not y:
        raise HTTPException(404, "堆区不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(y, field, value)
    db.commit()
    db.refresh(y)
    return api_response(message="已更新", data=_enrich_yard(db, y))


@router.post("/{yard_id}/maintenance")
def set_maintenance(
    yard_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_approver),
):
    y = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not y:
        raise HTTPException(404, "堆区不存在")
    if y.status != YardStatus.ACTIVE:
        raise HTTPException(400, "仅正常使用堆区可置为检修")
    y.status = YardStatus.MAINTENANCE
    db.commit()
    return api_response(message="已置为检修中")


@router.post("/{yard_id}/activate")
def activate(
    yard_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_approver),
):
    y = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not y:
        raise HTTPException(404, "堆区不存在")
    if y.status == YardStatus.ACTIVE:
        raise HTTPException(400, "堆区已是正常状态")
    y.status = YardStatus.ACTIVE
    db.commit()
    return api_response(message="已恢复使用")


@router.post("/{yard_id}/disable")
def disable(
    yard_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_approver),
):
    y = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not y:
        raise HTTPException(404, "堆区不存在")
    inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
        StockIn.yard_id == y.id
    ).scalar() or 0
    if inv > 0.1:
        raise HTTPException(400, f"堆区尚有 {inv:.1f} 吨库存，请先清空")
    y.status = YardStatus.DISABLED
    db.commit()
    return api_response(message="已停用")
