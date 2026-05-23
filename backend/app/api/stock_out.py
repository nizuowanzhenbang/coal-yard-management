"""出场登记 API（FIFO 扣减 + 大额审批）"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_write, require_approver
from app.config import settings
from app.models.stock_in import StockIn
from app.models.stock_out import StockOut, StockOutStatus
from app.models.yard import CoalYard, YardStatus
from app.models.user import User
from app.schemas.stock_out import StockOutCreate, StockOutApproval, StockOutResponse
from app.utils.helpers import api_response, paginate_response, generate_stockout_no
from app.utils.csv_export import stream_csv, fmt_dt

router = APIRouter(prefix="/api/stock-out", tags=["出场登记"])


def _enrich(s: StockOut) -> dict:
    result = StockOutResponse.model_validate(s).model_dump()
    if s.yard:
        result["yard_code"] = s.yard.code
        result["yard_name"] = s.yard.name
    return result


def _execute_fifo(db: Session, yard_id: int, quantity: float) -> list:
    """实际从 FIFO 队列扣减并返回明细。调用方需 commit。"""
    need = quantity
    batches = (
        db.query(StockIn)
        .filter(StockIn.yard_id == yard_id, StockIn.remaining_quantity > 0)
        .order_by(StockIn.stocked_at.asc())
        .all()
    )
    breakdown = []
    for b in batches:
        if need <= 0.001:
            break
        take = min(b.remaining_quantity, need)
        b.remaining_quantity = round(b.remaining_quantity - take, 3)
        need -= take
        breakdown.append({
            "stockin_no": b.stockin_no,
            "stocked_at": b.stocked_at.isoformat(),
            "taken": round(take, 3),
            "remaining_after": b.remaining_quantity,
        })
    return breakdown


@router.get("")
def list_stockouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    yard_id: Optional[int] = None,
    coal_type: Optional[str] = None,
    destination: Optional[str] = None,
    status: Optional[StockOutStatus] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(StockOut).options(joinedload(StockOut.yard))
    if yard_id:
        q = q.filter(StockOut.yard_id == yard_id)
    if coal_type:
        q = q.filter(StockOut.coal_type == coal_type)
    if destination:
        q = q.filter(StockOut.destination.like(f"%{destination}%"))
    if status:
        q = q.filter(StockOut.status == status)
    total = q.count()
    rows = (
        q.order_by(StockOut.delivered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return api_response(data=paginate_response([_enrich(r) for r in rows], total, page, page_size))


@router.get("/export")
def export_stockouts(
    yard_id: Optional[int] = None,
    coal_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(StockOut).options(joinedload(StockOut.yard))
    if yard_id:
        q = q.filter(StockOut.yard_id == yard_id)
    if coal_type:
        q = q.filter(StockOut.coal_type == coal_type)
    rows = q.order_by(StockOut.delivered_at.desc()).all()
    headers = ["出场单号", "堆区", "煤种", "出场量(吨)", "去向", "用途", "状态", "出场时间", "登记人", "审批人"]
    data = [
        [
            r.stockout_no, r.yard.name if r.yard else "", r.coal_type, r.quantity,
            r.destination, r.purpose or "", r.status.value,
            fmt_dt(r.delivered_at), r.operator or "", r.approver or "",
        ]
        for r in rows
    ]
    return stream_csv("出场记录", headers, data)


@router.post("")
def create_stockout(
    payload: StockOutCreate, db: Session = Depends(get_db),
    current: User = Depends(require_write),
):
    yard = db.query(CoalYard).filter(CoalYard.id == payload.yard_id).first()
    if not yard:
        raise HTTPException(404, "堆区不存在")
    if yard.status == YardStatus.DISABLED:
        raise HTTPException(400, "堆区已停用")
    if yard.designated_coal_type != payload.coal_type:
        raise HTTPException(400, f"堆区煤种为 {yard.designated_coal_type}，与请求煤种 {payload.coal_type} 不符")

    # 库存校验（即使大额需审批，提交时也要预校验防止纯空仓申请）
    current_inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
        StockIn.yard_id == yard.id
    ).scalar() or 0
    if payload.quantity > current_inv + 0.001:
        raise HTTPException(400, f"出场量超出当前库存（剩 {current_inv:.1f} 吨）")

    next_seq = (db.query(func.count(StockOut.id)).scalar() or 0) + 1
    requires_approval = payload.quantity >= settings.LARGE_STOCKOUT_THRESHOLD

    record = StockOut(
        stockout_no=generate_stockout_no(next_seq),
        operator=current.username,
        requires_approval=requires_approval,
        status=StockOutStatus.PENDING_APPROVAL if requires_approval else StockOutStatus.COMPLETED,
        **payload.model_dump(),
    )

    if not requires_approval:
        # 小额：立即 FIFO 扣减
        breakdown = _execute_fifo(db, yard.id, payload.quantity)
        record.fifo_breakdown = json.dumps(breakdown, ensure_ascii=False)
        msg = "出场已登记，FIFO 已扣减"
    else:
        msg = f"⚠ 大额出场（≥{settings.LARGE_STOCKOUT_THRESHOLD:.0f} 吨）已提交，等待主管审批后才会扣减库存"

    db.add(record)
    db.commit()
    db.refresh(record)
    return api_response(message=msg, data=_enrich(record))


@router.get("/{stockout_id}")
def get_stockout(stockout_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(StockOut).options(joinedload(StockOut.yard)).filter(StockOut.id == stockout_id).first()
    if not s:
        raise HTTPException(404, "出场记录不存在")
    return api_response(data=_enrich(s))


@router.post("/{stockout_id}/approve")
def approve_stockout(
    stockout_id: int, payload: StockOutApproval,
    db: Session = Depends(get_db), current: User = Depends(require_approver),
):
    """主管审批大额出场。通过则执行 FIFO 扣减；拒绝则保留记录不扣减。"""
    s = db.query(StockOut).filter(StockOut.id == stockout_id).first()
    if not s:
        raise HTTPException(404, "出场记录不存在")
    if s.status != StockOutStatus.PENDING_APPROVAL:
        raise HTTPException(400, "仅待审批出场单可审批")

    s.approver = current.username
    s.approved_at = datetime.utcnow()
    s.approval_notes = payload.approval_notes

    if payload.approved:
        # 复核库存（审批时点）
        current_inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
            StockIn.yard_id == s.yard_id
        ).scalar() or 0
        if s.quantity > current_inv + 0.001:
            raise HTTPException(400, f"审批时库存不足（剩 {current_inv:.1f} 吨），无法执行扣减")
        breakdown = _execute_fifo(db, s.yard_id, s.quantity)
        s.fifo_breakdown = json.dumps(breakdown, ensure_ascii=False)
        s.status = StockOutStatus.APPROVED
        msg = "审批通过，FIFO 已扣减"
    else:
        s.status = StockOutStatus.REJECTED
        msg = "已驳回，未扣减库存"

    db.commit()
    db.refresh(s)
    return api_response(message=msg, data=_enrich(s))
