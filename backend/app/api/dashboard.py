"""仪表盘 API"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.yard import CoalYard, YardStatus
from app.models.stock_in import StockIn
from app.models.stock_out import StockOut
from app.models.inventory_snapshot import InventorySnapshot
from app.models.stocktake import Stocktake, StocktakeStatus
from app.models.temperature import TemperatureReading
from app.models.user import User
from app.utils.helpers import api_response
from app.utils.coal_score import calc_score, blending_priority

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    now = datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_yards = db.query(func.count(CoalYard.id)).filter(
        CoalYard.status == YardStatus.ACTIVE
    ).scalar() or 0
    total_capacity = db.query(func.coalesce(func.sum(CoalYard.capacity), 0)).filter(
        CoalYard.status == YardStatus.ACTIVE
    ).scalar() or 0
    total_inventory = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).scalar() or 0
    utilization = (float(total_inventory) / float(total_capacity) * 100) if total_capacity else 0

    today_in = db.query(func.coalesce(func.sum(StockIn.quantity), 0)).filter(
        StockIn.stocked_at >= day_start
    ).scalar() or 0
    today_out = db.query(func.coalesce(func.sum(StockOut.quantity), 0)).filter(
        StockOut.delivered_at >= day_start
    ).scalar() or 0

    pending_stocktakes = db.query(func.count(Stocktake.id)).filter(
        Stocktake.status == StocktakeStatus.PENDING_APPROVAL
    ).scalar() or 0

    # 库龄红色批次
    danger_threshold = now - timedelta(days=settings.AGING_DANGER_DAYS)
    danger_qty = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
        StockIn.remaining_quantity > 0,
        StockIn.stocked_at < danger_threshold,
    ).scalar() or 0

    # 24h 内温度告警测点数（≥TEMP_ALERT）
    temp_since = now - timedelta(hours=24)
    hot_spots = db.query(func.count(TemperatureReading.id)).filter(
        TemperatureReading.measured_at >= temp_since,
        TemperatureReading.temperature >= settings.TEMP_ALERT,
    ).scalar() or 0

    return api_response(data={
        "active_yards": total_yards,
        "total_capacity": round(float(total_capacity), 1),
        "total_inventory": round(float(total_inventory), 1),
        "utilization": round(utilization, 1),
        "today_in_tons": round(float(today_in), 1),
        "today_out_tons": round(float(today_out), 1),
        "pending_stocktakes": pending_stocktakes,
        "aging_danger_tons": round(float(danger_qty), 1),
        "hot_spots_24h": hot_spots,
    })


@router.get("/yard-utilization")
def yard_utilization(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """各堆区容量利用率"""
    yards = db.query(CoalYard).filter(CoalYard.status != YardStatus.DISABLED).order_by(CoalYard.code).all()
    data = []
    for y in yards:
        inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
            StockIn.yard_id == y.id
        ).scalar() or 0
        data.append({
            "yard_code": y.code,
            "yard_name": y.name,
            "coal_type": y.designated_coal_type,
            "capacity": y.capacity,
            "inventory": round(float(inv), 1),
            "utilization": round(float(inv) / y.capacity * 100, 1) if y.capacity else 0,
            "status": y.status.value,
        })
    return api_response(data=data)


@router.get("/coal-type-inventory")
def coal_type_inventory(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """按煤种统计当前库存"""
    rows = (
        db.query(StockIn.coal_type, func.coalesce(func.sum(StockIn.remaining_quantity), 0).label("qty"))
        .filter(StockIn.remaining_quantity > 0)
        .group_by(StockIn.coal_type)
        .order_by(func.sum(StockIn.remaining_quantity).desc())
        .all()
    )
    return api_response(data=[
        {"coal_type": r[0], "inventory": round(float(r[1]), 1)} for r in rows
    ])


@router.get("/in-out-trend")
def in_out_trend(
    days: int = Query(30, ge=7, le=180),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """近 N 天进出趋势"""
    now = datetime.utcnow()
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    ins = db.query(StockIn).filter(StockIn.stocked_at >= start).all()
    outs = db.query(StockOut).filter(StockOut.delivered_at >= start).all()

    daily: dict = {}
    for i in ins:
        key = i.stocked_at.strftime("%Y-%m-%d")
        daily.setdefault(key, {"date": key, "in": 0.0, "out": 0.0})
        daily[key]["in"] += i.quantity
    for o in outs:
        key = o.delivered_at.strftime("%Y-%m-%d")
        daily.setdefault(key, {"date": key, "in": 0.0, "out": 0.0})
        daily[key]["out"] += o.quantity
    return api_response(data=sorted(
        [{"date": v["date"], "in": round(v["in"], 1), "out": round(v["out"], 1)} for v in daily.values()],
        key=lambda x: x["date"],
    ))


@router.get("/aging-alert")
def aging_alert(
    limit: int = Query(15, ge=5, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """库龄预警榜：按入场时间正序，取仍有剩余的最老批次"""
    now = datetime.utcnow()
    warn = settings.AGING_WARN_DAYS
    danger = settings.AGING_DANGER_DAYS
    rows = (
        db.query(StockIn)
        .options(joinedload(StockIn.yard))
        .filter(StockIn.remaining_quantity > 0)
        .order_by(StockIn.stocked_at.asc())
        .limit(limit)
        .all()
    )
    data = []
    for r in rows:
        days = (now - r.stocked_at).days
        if days <= warn:
            level = "green"
        elif days <= danger:
            level = "yellow"
        else:
            level = "red"
        data.append({
            "stockin_no": r.stockin_no,
            "yard_code": r.yard.code if r.yard else None,
            "yard_name": r.yard.name if r.yard else None,
            "coal_type": r.coal_type,
            "supplier_name": r.supplier_name,
            "stocked_at": r.stocked_at.isoformat(),
            "aging_days": days,
            "remaining_quantity": round(r.remaining_quantity, 1),
            "level": level,
        })
    return api_response(data=data)


@router.get("/blending-advice")
def blending_advice(
    limit: int = Query(10, ge=5, le=30),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """配煤建议：按综合评分 + 库龄权重排序，列出建议优先使用的批次"""
    now = datetime.utcnow()
    batches = (
        db.query(StockIn)
        .options(joinedload(StockIn.yard))
        .filter(StockIn.remaining_quantity > 0)
        .all()
    )
    data = []
    for b in batches:
        aging = (now - b.stocked_at).days
        score, breakdown = calc_score(b.calorific_value, b.ash, b.sulfur, b.moisture, aging)
        priority = blending_priority(score, aging)
        data.append({
            "stockin_no": b.stockin_no,
            "yard_code": b.yard.code if b.yard else None,
            "yard_name": b.yard.name if b.yard else None,
            "coal_type": b.coal_type,
            "remaining_quantity": round(b.remaining_quantity, 1),
            "calorific_value": b.calorific_value,
            "aging_days": aging,
            "current_score": score,
            "base_score": breakdown["base_score"],
            "aging_decay": breakdown["aging_decay"],
            "priority": priority,
        })
    data.sort(key=lambda x: -x["priority"])
    return api_response(data=data[:limit])


@router.get("/inventory-history")
def inventory_history(
    days: int = Query(30, ge=7, le=180),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """读取近 N 天快照，绘制库存趋势"""
    start = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            InventorySnapshot.snapshot_date,
            func.sum(InventorySnapshot.inventory).label("inv"),
        )
        .filter(InventorySnapshot.snapshot_date >= start)
        .group_by(InventorySnapshot.snapshot_date)
        .order_by(InventorySnapshot.snapshot_date)
        .all()
    )
    return api_response(data=[
        {"date": r[0].strftime("%Y-%m-%d"), "inventory": round(float(r[1]), 1)} for r in rows
    ])


@router.post("/snapshot")
def take_snapshot(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """手动触发当日库存快照（实际生产应由定时任务每日 0 点触发）"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # 当日已生成则跳过
    if db.query(InventorySnapshot).filter(InventorySnapshot.snapshot_date == today).first():
        return api_response(message="当日快照已存在，跳过")

    yards = db.query(CoalYard).all()
    now = datetime.utcnow()
    day_start = today
    for y in yards:
        inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
            StockIn.yard_id == y.id
        ).scalar() or 0
        in_24 = db.query(func.coalesce(func.sum(StockIn.quantity), 0)).filter(
            StockIn.yard_id == y.id,
            StockIn.stocked_at >= day_start,
        ).scalar() or 0
        out_24 = db.query(func.coalesce(func.sum(StockOut.quantity), 0)).filter(
            StockOut.yard_id == y.id,
            StockOut.delivered_at >= day_start,
        ).scalar() or 0
        oldest = (
            db.query(StockIn)
            .filter(StockIn.yard_id == y.id, StockIn.remaining_quantity > 0)
            .order_by(StockIn.stocked_at.asc())
            .first()
        )
        oldest_days = (now - oldest.stocked_at).days if oldest else None
        db.add(InventorySnapshot(
            snapshot_date=today,
            yard_id=y.id,
            yard_code=y.code,
            coal_type=y.designated_coal_type,
            inventory=round(float(inv), 1),
            capacity=y.capacity,
            utilization=round(float(inv) / y.capacity * 100, 1) if y.capacity else 0,
            in_24h=round(float(in_24), 1),
            out_24h=round(float(out_24), 1),
            oldest_in_days=oldest_days,
        ))
    db.commit()
    return api_response(message=f"已为 {len(yards)} 个堆区生成快照")
