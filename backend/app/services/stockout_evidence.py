"""只读账面FIFO依据，不认证物理煤流或上游化验身份。"""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from app.models.stock_out import StockOutStatus


def clean_input(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        return None
    if isinstance(value, list):
        return [clean_input(v) for v in value]
    if isinstance(value, dict):
        return {(clean_input(k) or '__invalid_key__'): clean_input(v) for k, v in value.items()}
    return value


def valid_text(value):
    if not isinstance(value, str) or not value.strip() or '\x00' in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError('无效文本')
    return value


class TimeDeclaration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    offset_minutes: Annotated[StrictInt, Field(ge=-840, le=840)]
    time_evidence: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator('time_evidence')
    @classmethod
    def text(cls, value):
        return valid_text(value)


def tonnes(value, positive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('吨数必须为数值')
    number = Decimal(str(value))
    if not number.is_finite() or number < 0 or number > Decimal('1000000000000') or (positive and number == 0):
        raise ValueError('吨数超出范围')
    if number % Decimal('0.001') != 0:
        raise ValueError('吨数须精确至0.001吨')
    return number


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('FIFO存在重复字段')
        result[key] = value
    return result


def timestamp(value, offset):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError('原始时间必须为无时区钟面时间')
    aware = value.replace(tzinfo=timezone(timedelta(minutes=offset)))
    aware.astimezone(timezone.utc)
    return aware.isoformat()


def export_accounting(incoming_by_no, row, declaration, instance, username):
    try:
        valid_text(instance)
        if len(instance) > 128 or instance != instance.strip():
            raise ValueError('来源实例非法')
    except ValueError as exc:
        raise HTTPException(503, '需配置有效YARD_SOURCE_INSTANCE') from exc
    if row.status not in (StockOutStatus.COMPLETED, StockOutStatus.APPROVED):
        raise HTTPException(409, '只有完成扣减的出场单可导出账面依据')
    try:
        amount = tonnes(row.quantity)
        items = json.loads(row.fifo_breakdown, object_pairs_hook=unique_object, parse_float=Decimal)
        if not isinstance(items, list) or not items:
            raise ValueError('无FIFO明细')
        seen, total, result = set(), Decimal(0), []
        for item in items:
            if not isinstance(item, dict) or set(item) != {'stockin_no', 'stocked_at', 'taken', 'remaining_after'}:
                raise ValueError('FIFO结构错误')
            reference = valid_text(item['stockin_no'])
            if reference in seen:
                raise ValueError('重复入场引用')
            seen.add(reference)
            incoming = incoming_by_no.get(reference)
            if incoming is None or incoming.yard_id != row.yard_id or incoming.coal_type != row.coal_type:
                raise ValueError('入场来源不一致')
            stored = datetime.fromisoformat(valid_text(item['stocked_at']))
            if stored != incoming.stocked_at or stored > row.delivered_at:
                raise ValueError('入场时间不一致或晚于出场')
            taken = tonnes(item['taken'])
            remaining = tonnes(item['remaining_after'], positive=False)
            total += taken
            result.append({'stockin_id': str(incoming.id), 'stockin_no': reference,
                           'stocked_at': timestamp(stored, declaration.offset_minutes),
                           'quantity_tonnes': f'{taken:.3f}', 'remaining_after_tonnes': f'{remaining:.3f}'})
        if total != amount:
            raise ValueError('FIFO扣减总量与出场量不一致')
        content = {'contract_version': 'yard-accounting/v1', 'evidence_kind': 'inventory_fifo_accounting',
                   'verification_scope': 'current_database_state_only', 'historical_source_identity_verified': False,
                   'source_system': 'coal-yard-management', 'source_instance': instance,
                   'stockout_id': str(row.id), 'stockout_no': valid_text(row.stockout_no),
                   'yard_id': str(row.yard_id), 'coal_type': valid_text(row.coal_type),
                   'quantity_tonnes': f'{amount:.3f}', 'destination_text': valid_text(row.destination),
                   'delivered_at': timestamp(row.delivered_at, declaration.offset_minutes),
                   'status': row.status.value, 'fifo': result,
                   'time_provenance': {'kind': 'caller_declared_offset', 'offset_minutes': declaration.offset_minutes,
                                       'evidence': declaration.time_evidence, 'declared_by': valid_text(username),
                                       'stored_time': row.delivered_at.isoformat()}}
        encoded = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        return {**content, 'content_sha256': hashlib.sha256(encoded.encode('utf-8')).hexdigest()}
    except (ValueError, TypeError, KeyError, OverflowError, InvalidOperation, RecursionError) as exc:
        raise HTTPException(409, '账面出场依据不完整或不一致，需核查原记录') from exc
