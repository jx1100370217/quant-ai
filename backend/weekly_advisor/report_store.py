"""周推荐报告的本地持久化与可审计推荐流水。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import WeeklyReport


_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "cache" / "weekly_reports"


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def save_weekly_report(report: WeeklyReport, base_dir: Optional[Path] = None) -> Path:
    """原子保存最新报告，并追加一条不可覆盖的推荐审计记录。"""
    directory = Path(base_dir) if base_dir is not None else _DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump()
    generated_at = report.generated_at or datetime.now().isoformat(timespec="seconds")
    payload["generated_at"] = generated_at

    safe_ts = generated_at.replace(":", "-")
    unique_suffix = datetime.now().strftime("%f")
    report_path = directory / f"report-{safe_ts}-{unique_suffix}.json"
    _atomic_write_json(report_path, payload)
    _atomic_write_json(directory / "latest.json", payload)

    ledger_record = {
        "generated_at": generated_at,
        "strategy_version": report.strategy_version,
        "target_week": report.target_week,
        "total_candidates_scanned": report.total_candidates_scanned,
        "market_cap_eligible": report.market_cap_eligible,
        "kline_evaluated": report.kline_evaluated,
        "scan_data_complete": report.scan_data_complete,
        "scan_metrics_version": report.scan_metrics_version,
        "invested_position_pct": report.invested_position_pct,
        "cash_position_pct": report.cash_position_pct,
        "recommendations": [
            {
                "rank": rank,
                "code": rec.code,
                "name": rec.name,
                "position_pct": rec.position_pct,
                "signal_score": rec.confidence,
                "reversal_score": rec.reversal_score,
                "bounce_pct": rec.bounce_pct,
                "decline_7d": rec.decline_7d,
                "vol_ratio": rec.vol_ratio,
                "rsi6": rec.rsi6,
            }
            for rank, rec in enumerate(report.recommendations, 1)
        ],
    }
    with (directory / "recommendation-ledger.jsonl").open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(ledger_record, ensure_ascii=False) + "\n")
    return report_path


def load_latest_report(base_dir: Optional[Path] = None) -> Optional[WeeklyReport]:
    """读取最近一次持久化报告；文件损坏时安全返回 None。"""
    directory = Path(base_dir) if base_dir is not None else _DEFAULT_DIR
    path = directory / "latest.json"
    if not path.exists():
        return None
    try:
        return WeeklyReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None
