"""CSV 导出工具（UTF-8 BOM）"""
import csv
import io
from datetime import datetime
from typing import Iterable, List
from urllib.parse import quote

from fastapi.responses import StreamingResponse


def stream_csv(filename: str, headers: List[str], rows: Iterable[list]) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    buf.seek(0)
    stamped = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    encoded = quote(stamped)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def fmt_date(dt) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""
