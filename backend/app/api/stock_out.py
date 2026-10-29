"""出场登记 API（FIFO 扣减 + 大额审批）"""
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
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
    need = Decimal(str(quantity))
    batches = (db.query(StockIn)
               .filter(StockIn.yard_id == yard_id, StockIn.remaining_quantity > 0)
               .order_by(StockIn.stocked_at.asc(), StockIn.id.asc()).all())
    breakdown = []
    for batch in batches:
        if need == 0:
            break
        available = _stored_quantity(batch.remaining_quantity)
        take = min(available, need)
        remaining = available - take
        batch.remaining_quantity = float(remaining)
        need -= take
        breakdown.append({"stockin_no": batch.stockin_no, "stocked_at": batch.stocked_at.isoformat(),
                          "taken": float(take), "remaining_after": float(remaining)})
    if need != 0:
        raise HTTPException(409, "库存明细不足，出场未执行")
    return breakdown


def _stored_quantity(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number % Decimal('0.001') != 0:
            raise ValueError('库存数量不符合千分吨精度')
        return number
    except (ValueError, InvalidOperation) as exc:
        raise HTTPException(409, "库存明细无效，需先核查") from exc


def _available_inventory(db, yard_id):
    rows = db.query(StockIn.remaining_quantity).filter(StockIn.yard_id == yard_id).all()
    return sum((_stored_quantity(row[0]) for row in rows), Decimal(0))


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
    current_inv = _available_inventory(db, yard.id)
    if Decimal(str(payload.quantity)) > current_inv:
        raise HTTPException(400, f"出场量超出当前库存（剩 {current_inv:.3f} 吨）")

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
        current_inv = _available_inventory(db, s.yard_id)
        if _stored_quantity(s.quantity) <= 0 or _stored_quantity(s.quantity) > current_inv:
            raise HTTPException(400, f"审批时库存不足或数量无效（剩 {current_inv:.3f} 吨）")
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


from typing import Annotated
from pydantic import BeforeValidator
from app.services.stockout_evidence import TimeDeclaration, clean_input, export_accounting


@router.post("/{stockout_id}/accounting-evidence")
def accounting_evidence(
    stockout_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    payload: Annotated[TimeDeclaration, BeforeValidator(clean_input)],
    db: Session = Depends(get_db), current: User = Depends(get_current_user),
):
    # 一条数据库语句读取出场及所在堆区入场记录，避免逐条查询拼接不同时间的状态。
    records = (db.query(StockOut, StockIn).outerjoin(StockIn, StockIn.yard_id == StockOut.yard_id)
               .filter(StockOut.id == stockout_id).all())
    if not records:
        raise HTTPException(404, "出场记录不存在")
    row = records[0][0]
    incoming_by_no = {incoming.stockin_no: incoming for _, incoming in records if incoming is not None}
    return api_response(data=export_accounting(incoming_by_no, row, payload, settings.YARD_SOURCE_INSTANCE, current.username))
