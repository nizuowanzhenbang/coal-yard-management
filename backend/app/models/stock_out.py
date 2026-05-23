"""出场记录模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class StockOutStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"  # 大额，待审批（未扣减）
    APPROVED = "APPROVED"                   # 大额已通过，已扣减
    REJECTED = "REJECTED"                   # 大额被拒，未扣减
    COMPLETED = "COMPLETED"                 # 小额，自动通过 + 已扣减


class StockOut(Base):
    """煤炭出场记录（上煤至锅炉/磨煤机）。
    大额（>= LARGE_STOCKOUT_THRESHOLD）创建即 PENDING_APPROVAL 不扣减，
    审批通过后才执行 FIFO 扣减。小额自动 COMPLETED。
    """
    __tablename__ = "stock_outs"

    id = Column(Integer, primary_key=True, index=True)
    stockout_no = Column(String(50), unique=True, index=True, nullable=False, comment="出场单号")
    yard_id = Column(Integer, ForeignKey("coal_yards.id"), nullable=False, index=True)

    coal_type = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False, comment="出场量（吨）")

    # 去向
    destination = Column(String(100), nullable=False, comment="去向：#1机组/#2磨煤机/...")
    purpose = Column(String(50), nullable=True, comment="用途：发电/调试")

    delivered_at = Column(DateTime, nullable=False, index=True, comment="出场时间")
    operator = Column(String(50), nullable=True)

    # FIFO 扣减明细（JSON 文本，记录从哪几条入场扣减了多少）
    fifo_breakdown = Column(Text, nullable=True, comment="FIFO 扣减明细 JSON")

    # 审批相关
    requires_approval = Column(Boolean, default=False, nullable=False, comment="是否需要主管审批（大额）")
    status = Column(Enum(StockOutStatus), default=StockOutStatus.COMPLETED, nullable=False, index=True)
    approver = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    yard = relationship("CoalYard", back_populates="stock_outs")
