"""入场记录模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class StockIn(Base):
    """煤炭入场记录（一条订单可能分多条入场）"""
    __tablename__ = "stock_ins"

    id = Column(Integer, primary_key=True, index=True)
    stockin_no = Column(String(50), unique=True, index=True, nullable=False, comment="入场单号")
    yard_id = Column(Integer, ForeignKey("coal_yards.id"), nullable=False, index=True)

    # 来源（关联 fuel-procurement 订单）
    order_no = Column(String(50), nullable=True, index=True, comment="采购订单号")
    supplier_name = Column(String(200), nullable=True, comment="供应商")
    contract_no = Column(String(50), nullable=True)

    # 煤种和数量
    coal_type = Column(String(50), nullable=False, comment="煤种")
    quantity = Column(Float, nullable=False, comment="入场量（吨）")

    # 煤质标签（从 coal-quality-monitor 拉取或人工录入）
    calorific_value = Column(Float, nullable=True, comment="热值 kcal/kg")
    ash = Column(Float, nullable=True, comment="灰分 %")
    sulfur = Column(Float, nullable=True, comment="硫分 %")
    moisture = Column(Float, nullable=True, comment="水分 %")
    quality_synced = Column(Boolean, default=False, comment="是否已从化验系统同步")

    # 入场信息
    stocked_at = Column(DateTime, nullable=False, index=True, comment="入场时间")
    operator = Column(String(50), nullable=True, comment="登记人")
    transport_mode = Column(String(50), nullable=True, comment="运输方式")

    # FIFO 库龄追踪：剩余可出场量（出场时从最早的入场记录扣减）
    remaining_quantity = Column(Float, nullable=False, comment="剩余库存量（吨，FIFO）")

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    yard = relationship("CoalYard", back_populates="stock_ins")
