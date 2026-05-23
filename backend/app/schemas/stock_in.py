"""入场记录 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class StockInCreate(BaseModel):
    yard_id: int
    order_no: Optional[str] = None      # 关联 fuel-procurement 订单（可选）
    supplier_name: Optional[str] = None
    contract_no: Optional[str] = None
    coal_type: str
    quantity: float
    stocked_at: datetime
    transport_mode: Optional[str] = None
    calorific_value: Optional[float] = None
    ash: Optional[float] = None
    sulfur: Optional[float] = None
    moisture: Optional[float] = None
    notes: Optional[str] = None


class StockInUpdate(BaseModel):
    coal_type: Optional[str] = None
    calorific_value: Optional[float] = None
    ash: Optional[float] = None
    sulfur: Optional[float] = None
    moisture: Optional[float] = None
    notes: Optional[str] = None


class StockInResponse(BaseModel):
    id: int
    stockin_no: str
    yard_id: int
    yard_code: Optional[str] = None
    yard_name: Optional[str] = None
    order_no: Optional[str]
    supplier_name: Optional[str]
    contract_no: Optional[str]
    coal_type: str
    quantity: float
    remaining_quantity: float
    calorific_value: Optional[float]
    ash: Optional[float]
    sulfur: Optional[float]
    moisture: Optional[float]
    quality_synced: bool
    stocked_at: datetime
    operator: Optional[str]
    transport_mode: Optional[str]
    notes: Optional[str]
    created_at: datetime
    aging_days: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
