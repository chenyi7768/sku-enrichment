"""SKU Catalog Enrichment — local demo MVP (FastAPI)."""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from enrichment.pipeline import enrich_dataframe, parse_upload

BASE = Path(__file__).resolve().parent
SAMPLE_XLSX = BASE / "sample_data" / "building_supply_skus.xlsx"

app = FastAPI(title="SKU目录智能富化", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

# In-memory store for download tokens (demo only)
_RESULTS: dict[str, pd.DataFrame] = {}


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/enrich")
async def enrich(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "请选择文件")
    lower = file.filename.lower()
    if not lower.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "仅支持 .xlsx / .csv 文件")
    content = await file.read()
    if not content:
        raise HTTPException(400, "文件为空")
    try:
        df = parse_upload(content, file.filename)
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}") from e
    if df.empty:
        raise HTTPException(400, "表格中没有数据行")
    if len(df) > 500:
        raise HTTPException(
            400,
            f"单次最多支持 500 行，当前文件有 {len(df)} 行，请拆分后重新上传（不会截断处理）",
        )

    enriched, meta = enrich_dataframe(df)
    token = uuid.uuid4().hex
    _RESULTS[token] = enriched

    preview = enriched.head(50).to_dict(orient="records")
    return {
        "ok": True,
        "token": token,
        "meta": meta,
        "preview": preview,
        "total": len(enriched),
        "preview_count": len(preview),
    }


@app.post("/api/enrich-sample")
async def enrich_sample():
    if not SAMPLE_XLSX.exists():
        raise HTTPException(500, "样例文件缺失，请先运行 generate_sample.py")
    content = SAMPLE_XLSX.read_bytes()
    df = parse_upload(content, SAMPLE_XLSX.name)
    enriched, meta = enrich_dataframe(df)
    token = uuid.uuid4().hex
    _RESULTS[token] = enriched
    preview = enriched.head(50).to_dict(orient="records")
    return {
        "ok": True,
        "token": token,
        "meta": meta,
        "preview": preview,
        "total": len(enriched),
        "preview_count": len(preview),
        "sample": True,
    }


@app.get("/api/download/{token}")
async def download(token: str):
    df = _RESULTS.get(token)
    if df is None:
        raise HTTPException(404, "结果已过期，请重新上传")
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="enriched_skus.csv"'},
    )


@app.get("/api/sample-file")
async def sample_file():
    if not SAMPLE_XLSX.exists():
        raise HTTPException(404, "样例文件不存在")
    return StreamingResponse(
        io.BytesIO(SAMPLE_XLSX.read_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="building_supply_skus.xlsx"'},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
