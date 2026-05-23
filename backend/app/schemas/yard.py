"""堆区 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.yard import YardStatus


class YardCreate(BaseModel):
    name: str
    designated_coal_type: str
    capacity: float
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    notes: Optional[str] = None


class YardUpdate(BaseModel):
    name: Optional[str] = None
    designated_coal_type: Optional[str] = None
    capacity: Optional[float] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    notes: Optional[str] = None


class YardResponse(BaseModel):
    id: int
    code: str
    name: str
    designated_coal_type: str
    capacity: float
    location: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    status: YardStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # 运行时计算字段
    current_inventory: Optional[float] = None
    utilization: Optional[float] = None
    oldest_in_days: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
