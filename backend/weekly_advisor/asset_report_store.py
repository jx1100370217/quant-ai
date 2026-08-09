"""非个股周推荐报告的通用持久化与审计流水。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel


_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "cache" / "weekly_reports"
ReportT = TypeVar("ReportT", bound=BaseModel)


def _asset_directory(asset: str, base_dir: Optional[Path] = None) -> Path:
    root = Path(base_dir) if base_dir is not None else _DEFAULT_DIR
    if asset not in {"fund", "bitcoin", "crypto"}:
        raise ValueError(f"不支持的资产类型: {asset}")
    return root / asset


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def save_asset_report(report: BaseModel, asset: str, base_dir: Optional[Path] = None) -> Path:
    """原子保存最新报告，并追加一条仅追加的审计记录。"""
    directory = _asset_directory(asset, base_dir)
    directory.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump()
    generated_at = payload.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    payload["generated_at"] = generated_at

    safe_ts = generated_at.replace(":", "-")
    unique_suffix = datetime.now().strftime("%f")
    report_path = directory / f"report-{safe_ts}-{unique_suffix}.json"
    _atomic_write_json(report_path, payload)
    _atomic_write_json(directory / "latest.json", payload)

    ledger_record = {
        "asset": asset,
        "generated_at": generated_at,
        "target_week": payload.get("target_week"),
        "strategy_version": payload.get("strategy_version"),
        "report": payload,
    }
    with (directory / "recommendation-ledger.jsonl").open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(ledger_record, ensure_ascii=False) + "\n")
    return report_path


def load_latest_asset_report(
    model: Type[ReportT], asset: str, base_dir: Optional[Path] = None
) -> Optional[ReportT]:
    """读取最近一次报告；文件不存在或损坏时返回 None。"""
    path = _asset_directory(asset, base_dir) / "latest.json"
    if not path.exists():
        return None
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None
