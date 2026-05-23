"""盘点单模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class StocktakeStatus(str, enum.Enum):
    DRAFT = "DRAFT"             # 草稿（已实测，待提交）
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"       # 已审批，调差已应用
    REJECTED = "REJECTED"


class Stocktake(Base):
    """堆区盘点单。实测值 vs 账面值，差异需要主管审批后才能调账。"""
    __tablename__ = "stocktakes"

    id = Column(Integer, primary_key=True, index=True)
    stocktake_no = Column(String(50), unique=True, index=True, nullable=False, comment="盘点单号")
    yard_id = Column(Integer, ForeignKey("coal_yards.id"), nullable=False, index=True)

    book_inventory = Column(Float, nullable=False, comment="账面库存（吨）")
    actual_inventory = Column(Float, nullable=False, comment="实测库存（吨）")
    diff_quantity = Column(Float, nullable=False, comment="差异量（实测-账面）")
    diff_rate = Column(Float, nullable=False, comment="差异率 %")

    measured_at = Column(DateTime, nullable=False, comment="盘点时间")
    measurer = Column(String(50), nullable=True, comment="盘点人")
    method = Column(String(50), nullable=True, comment="测量方法：激光扫描/无人机/人工估算")
    reason = Column(Text, nullable=True, comment="差异原因")

    status = Column(Enum(StocktakeStatus), default=StocktakeStatus.DRAFT, nullable=False, index=True)
    approver = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    yard = relationship("CoalYard", back_populates="stocktakes")
