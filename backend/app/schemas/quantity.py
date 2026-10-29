"""入场、出场和盘点统一使用有限、千分吨精度的输入。"""
import math
from decimal import Decimal, InvalidOperation
from typing import Annotated
from pydantic import BeforeValidator, Field


def checked(value):
    if isinstance(value, bool):
        raise ValueError('数量不能是布尔值')
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)  # 由后续有限数校验拒绝，避免JSON错误详情包含非有限数
    try:
        number = Decimal(str(value))
        if number.is_finite() and (number > Decimal('1000000000000') or
                                   number < 0 or number % Decimal('0.001') != 0):
            raise ValueError('数量超出范围或超过三位小数')
    except InvalidOperation as exc:
        raise ValueError('数量格式无效') from exc
    return value


MovementQuantity = Annotated[float, BeforeValidator(checked), Field(gt=0, le=1_000_000_000_000, allow_inf_nan=False)]
InventoryQuantity = Annotated[float, BeforeValidator(checked), Field(ge=0, le=1_000_000_000_000, allow_inf_nan=False)]
