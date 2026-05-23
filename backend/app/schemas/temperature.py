"""温度测量 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.temperature import TemperatureSource


class TemperatureCreate(BaseModel):
    yard_id: int
    spot: str
    temperature: float
    source: TemperatureSource = TemperatureSource.MANUAL
    measured_at: datetime
    notes: Optional[str] = None


class TemperatureResponse(BaseModel):
    id: int
    yard_id: int
    yard_code: Optional[str] = None
    yard_name: Optional[str] = None
    spot: str
    temperature: float
    source: TemperatureSource
    measured_at: datetime
    operator: Optional[str]
    notes: Optional[str]
    created_at: datetime
    level: Optional[str] = None  # green/warn/alert/danger
    model_config = ConfigDict(from_attributes=True)
