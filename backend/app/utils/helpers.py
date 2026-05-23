"""通用工具"""
from datetime import datetime
from typing import Any


def api_response(data: Any = None, message: str = "ok", code: int = 200) -> dict:
    return {"code": code, "message": message, "data": data}


def paginate_response(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
    }


def generate_yard_code(seq: int) -> str:
    return f"DQ-{seq:03d}"


def generate_stockin_no(seq: int) -> str:
    return f"IN-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"


def generate_stockout_no(seq: int) -> str:
    return f"OUT-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"


def generate_stocktake_no(seq: int) -> str:
    return f"PD-{datetime.now().strftime('%Y%m%d')}-{seq:03d}"
