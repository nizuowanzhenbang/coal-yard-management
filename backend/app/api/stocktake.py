"""盘点 API"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_write, require_approver
from app.models.stock_in import StockIn
from app.models.stocktake import Stocktake, StocktakeStatus
from app.models.yard import CoalYard
from app.models.user import User
from app.schemas.stocktake import StocktakeCreate, StocktakeApproval, StocktakeResponse
from app.utils.helpers import api_response, paginate_response, generate_stocktake_no

router = APIRouter(prefix="/api/stocktake", tags=["盘点"])


def _enrich(s: Stocktake) -> dict:
    result = StocktakeResponse.model_validate(s).model_dump()
    if s.yard:
        result["yard_code"] = s.yard.code
        result["yard_name"] = s.yard.name
    return result


def _current_book_inventory(db: Session, yard_id: int) -> float:
    inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
        StockIn.yard_id == yard_id
    ).scalar() or 0
    return float(inv)


@router.get("")
def list_stocktakes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    yard_id: Optional[int] = None,
    status: Optional[StocktakeStatus] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Stocktake).options(joinedload(Stocktake.yard))
    if yard_id:
        q = q.filter(Stocktake.yard_id == yard_id)
    if status:
        q = q.filter(Stocktake.status == status)
    total = q.count()
    rows = (
        q.order_by(Stocktake.measured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return api_response(data=paginate_response([_enrich(r) for r in rows], total, page, page_size))


@router.post("")
def create_stocktake(
    payload: StocktakeCreate, db: Session = Depends(get_db),
    current: User = Depends(require_write),
):
    yard = db.query(CoalYard).filter(CoalYard.id == payload.yard_id).first()
    if not yard:
        raise HTTPException(404, "堆区不存在")
    book = _current_book_inventory(db, yard.id)
    diff = round(payload.actual_inventory - book, 3)
    diff_rate = round(diff / book * 100, 2) if book > 0 else 0.0

    next_seq = (db.query(func.count(Stocktake.id)).scalar() or 0) + 1
    record = Stocktake(
        stocktake_no=generate_stocktake_no(next_seq),
        yard_id=yard.id,
        book_inventory=round(book, 3),
        actual_inventory=payload.actual_inventory,
        diff_quantity=diff,
        diff_rate=diff_rate,
        measured_at=payload.measured_at,
        measurer=current.username,
        method=payload.method,
        reason=payload.reason,
        status=StocktakeStatus.PENDING_APPROVAL,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return api_response(message="盘点单已提交，待主管审批", data=_enrich(record))


@router.get("/{stocktake_id}")
def get_stocktake(stocktake_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(Stocktake).options(joinedload(Stocktake.yard)).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    return api_response(data=_enrich(s))


@router.post("/{stocktake_id}/approve")
def approve_stocktake(
    stocktake_id: int, payload: StocktakeApproval,
    db: Session = Depends(get_db), current: User = Depends(require_approver),
):
    """审批盘点：通过则按差异比例调整堆区所有有剩余的批次（按比例缩放）。"""
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    if s.status != StocktakeStatus.PENDING_APPROVAL:
        raise HTTPException(400, "仅待审批盘点单可审批")

    s.approver = current.username
    s.approved_at = datetime.utcnow()
    s.approval_notes = payload.approval_notes

    if payload.approved:
        # 按比例调整：以盘点时间点的账面为基准
        if s.book_inventory > 0:
            ratio = s.actual_inventory / s.book_inventory
            batches = (
                db.query(StockIn)
                .filter(StockIn.yard_id == s.yard_id, StockIn.remaining_quantity > 0)
                .all()
            )
            for b in batches:
                b.remaining_quantity = round(b.remaining_quantity * ratio, 3)
        s.status = StocktakeStatus.APPROVED
        msg = f"已审批，差异 {s.diff_quantity:+.1f} 吨已按比例调账"
    else:
        s.status = StocktakeStatus.REJECTED
        msg = "已驳回，差异未调账"

    db.commit()
    db.refresh(s)
    return api_response(message=msg, data=_enrich(s))


@router.get("/yard/{yard_id}/book-inventory")
def get_book_inventory(yard_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取堆区当前账面库存（创建盘点单前的辅助接口）"""
    yard = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not yard:
        raise HTTPException(404, "堆区不存在")
    return api_response(data={
        "yard_id": yard.id,
        "yard_code": yard.code,
        "yard_name": yard.name,
        "book_inventory": round(_current_book_inventory(db, yard.id), 3),
    })
