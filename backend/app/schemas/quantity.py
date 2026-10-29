"""入场、出场和盘点统一使用有限、千分吨精度的输入。"""
import math
from decimal import Decimal
from typing import Annotated
from pydantic import AfterValidator, BeforeValidator, Field


def normalize(value):
    if isinstance(value, bool):
        raise ValueError('数量不能是布尔值')
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def exact_thousandth(value):
    if Decimal(str(value)) % Decimal('0.001') != 0:
        raise ValueError('数量最多保留三位小数')
    return value


MovementQuantity = Annotated[float, BeforeValidator(normalize), Field(gt=0, le=1_000_000_000_000, allow_inf_nan=False), AfterValidator(exact_thousandth)]
InventoryQuantity = Annotated[float, BeforeValidator(normalize), Field(ge=0, le=1_000_000_000_000, allow_inf_nan=False), AfterValidator(exact_thousandth)]
