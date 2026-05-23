"""温度监控 API"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_write
from app.config import settings
from app.models.temperature import TemperatureReading
from app.models.yard import CoalYard
from app.models.user import User
from app.schemas.temperature import TemperatureCreate, TemperatureResponse
from app.utils.helpers import api_response, paginate_response

router = APIRouter(prefix="/api/temperature", tags=["温度监控"])


def _level(t: float) -> str:
    if t >= settings.TEMP_DANGER:
        return "danger"
    if t >= settings.TEMP_ALERT:
        return "alert"
    if t >= settings.TEMP_WARN:
        return "warn"
    return "green"


def _enrich(r: TemperatureReading) -> dict:
    result = TemperatureResponse.model_validate(r).model_dump()
    if r.yard:
        result["yard_code"] = r.yard.code
        result["yard_name"] = r.yard.name
    result["level"] = _level(r.temperature)
    return result


@router.get("")
def list_readings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    yard_id: Optional[int] = None,
    min_temp: Optional[float] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(TemperatureReading).options(joinedload(TemperatureReading.yard))
    if yard_id:
        q = q.filter(TemperatureReading.yard_id == yard_id)
    if min_temp is not None:
        q = q.filter(TemperatureReading.temperature >= min_temp)
    total = q.count()
    rows = (
        q.order_by(TemperatureReading.measured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return api_response(data=paginate_response([_enrich(r) for r in rows], total, page, page_size))


@router.post("")
def create_reading(
    payload: TemperatureCreate, db: Session = Depends(get_db),
    current: User = Depends(require_write),
):
    yard = db.query(CoalYard).filter(CoalYard.id == payload.yard_id).first()
    if not yard:
        raise HTTPException(404, "堆区不存在")
    if payload.temperature < -50 or payload.temperature > 500:
        raise HTTPException(400, "温度数值异常")
    record = TemperatureReading(
        operator=current.username,
        **payload.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    lv = _level(record.temperature)
    msg = "温度已录入"
    if lv == "danger":
        msg = "⚠ 温度危险（≥80℃ 接近自燃点），请立即处置！"
    elif lv == "alert":
        msg = "⚠ 温度告警（≥65℃），建议倒堆/喷水降温"
    elif lv == "warn":
        msg = "温度预警（≥50℃），加强观察"
    return api_response(message=msg, data=_enrich(record))


@router.delete("/{reading_id}")
def delete_reading(
    reading_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_write),
):
    r = db.query(TemperatureReading).filter(TemperatureReading.id == reading_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    db.delete(r)
    db.commit()
    return api_response(message="已删除")


@router.get("/hotspots")
def hotspots(
    limit: int = Query(10, ge=5, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """高温测点榜单：每个 (堆区, 测点) 取最近 24h 内最高温度"""
    since = datetime.utcnow() - timedelta(hours=24)
    sub = (
        db.query(
            TemperatureReading.yard_id,
            TemperatureReading.spot,
            func.max(TemperatureReading.temperature).label("max_temp"),
        )
        .filter(TemperatureReading.measured_at >= since)
        .group_by(TemperatureReading.yard_id, TemperatureReading.spot)
        .subquery()
    )
    rows = (
        db.query(TemperatureReading)
        .options(joinedload(TemperatureReading.yard))
        .join(
            sub,
            (TemperatureReading.yard_id == sub.c.yard_id)
            & (TemperatureReading.spot == sub.c.spot)
            & (TemperatureReading.temperature == sub.c.max_temp)
            & (TemperatureReading.measured_at >= since),
        )
        .order_by(TemperatureReading.temperature.desc())
        .limit(limit)
        .all()
    )
    return api_response(data=[_enrich(r) for r in rows])


@router.get("/yard/{yard_id}/trend")
def yard_trend(
    yard_id: int,
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """堆区温度趋势：取每日各测点最高温"""
    yard = db.query(CoalYard).filter(CoalYard.id == yard_id).first()
    if not yard:
        raise HTTPException(404, "堆区不存在")
    start = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(TemperatureReading)
        .filter(TemperatureReading.yard_id == yard_id, TemperatureReading.measured_at >= start)
        .order_by(TemperatureReading.measured_at.asc())
        .all()
    )
    daily: dict = {}
    for r in rows:
        key = r.measured_at.strftime("%Y-%m-%d")
        daily.setdefault(key, []).append(r.temperature)
    return api_response(data=[
        {
            "date": k,
            "max_temp": round(max(v), 1),
            "avg_temp": round(sum(v) / len(v), 1),
            "min_temp": round(min(v), 1),
            "samples": len(v),
        }
        for k, v in sorted(daily.items())
    ])
