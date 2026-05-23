"""盘点单 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.stocktake import StocktakeStatus


class StocktakeCreate(BaseModel):
    yard_id: int
    actual_inventory: float
    measured_at: datetime
    method: Optional[str] = None
    reason: Optional[str] = None


class StocktakeApproval(BaseModel):
    approved: bool
    approval_notes: Optional[str] = None


class StocktakeResponse(BaseModel):
    id: int
    stocktake_no: str
    yard_id: int
    yard_code: Optional[str] = None
    yard_name: Optional[str] = None
    book_inventory: float
    actual_inventory: float
    diff_quantity: float
    diff_rate: float
    measured_at: datetime
    measurer: Optional[str]
    method: Optional[str]
    reason: Optional[str]
    status: StocktakeStatus
    approver: Optional[str]
    approved_at: Optional[datetime]
    approval_notes: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
