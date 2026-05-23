"""出场记录 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.stock_out import StockOutStatus


class StockOutCreate(BaseModel):
    yard_id: int
    coal_type: str
    quantity: float
    destination: str
    purpose: Optional[str] = None
    delivered_at: datetime
    notes: Optional[str] = None


class StockOutApproval(BaseModel):
    approved: bool
    approval_notes: Optional[str] = None


class StockOutResponse(BaseModel):
    id: int
    stockout_no: str
    yard_id: int
    yard_code: Optional[str] = None
    yard_name: Optional[str] = None
    coal_type: str
    quantity: float
    destination: str
    purpose: Optional[str]
    delivered_at: datetime
    operator: Optional[str]
    fifo_breakdown: Optional[str]
    requires_approval: bool
    status: StockOutStatus
    approver: Optional[str]
    approved_at: Optional[datetime]
    approval_notes: Optional[str]
    notes: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
