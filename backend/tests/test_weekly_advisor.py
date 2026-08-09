from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

from weekly_advisor import portfolio_monitor
from data import eastmoney
from weekly_advisor.models import StockRecommendation, WeeklyReport
from weekly_advisor.portfolio_monitor import _portfolio_window_state, _target_week_bounds
from weekly_advisor.report_store import load_latest_report, save_weekly_report
from weekly_advisor.strategy import STRATEGY, allocate_rank_weights


def _recommendation(code: str, position_pct: float) -> StockRecommendation:
    return StockRecommendation(
        code=code,
        name=f"测试{code}",
        current_price=10.0,
        target_price=10.5,
        stop_loss_price=9.4,
        position_pct=position_pct,
        buy_reason="规则证据",
        risk_note="测试风险",
        reversal_reason="仅使用已提供指标",
        reversal_score=55.0,
        confidence=55.0,
        bounce_pct=4.0,
        decline_7d=-8.0,
        vol_ratio=1.8,
        rsi6=40.0,
    )


class StrategyAllocationTests(unittest.TestCase):
    def test_sparse_candidates_keep_cash(self) -> None:
        self.assertEqual(allocate_rank_weights(0), ([], 100.0))
        self.assertEqual(allocate_rank_weights(1), ([35.0], 65.0))
        self.assertEqual(allocate_rank_weights(2), ([35.0, 25.0], 40.0))
        self.assertEqual(allocate_rank_weights(3), ([35.0, 25.0, 20.0], 20.0))

    def test_five_candidates_use_full_rank_budget(self) -> None:
        weights, cash = allocate_rank_weights(5)
        self.assertEqual(weights, [35.0, 25.0, 20.0, 12.0, 8.0])
        self.assertEqual(sum(weights), 100.0)
        self.assertEqual(cash, 0.0)

    def test_allocation_rejects_negative_count(self) -> None:
        with self.assertRaises(ValueError):
            allocate_rank_weights(-1)


class PortfolioWindowTests(unittest.TestCase):
    def test_monitor_only_runs_inside_target_week(self) -> None:
        target = "2026-08-10 ~ 2026-08-14"
        self.assertEqual(
            _portfolio_window_state(target, date(2026, 8, 9)),
            "not_started",
        )
        self.assertEqual(
            _portfolio_window_state(target, date(2026, 8, 12)),
            "active",
        )
        self.assertEqual(
            _portfolio_window_state(target, date(2026, 8, 15)),
            "expired",
        )

    def test_invalid_or_reversed_target_week_is_rejected(self) -> None:
        self.assertIsNone(_target_week_bounds("bad-week"))
        self.assertIsNone(_target_week_bounds("2026-08-14 ~ 2026-08-10"))
        self.assertEqual(_portfolio_window_state("bad-week", date(2026, 8, 12)), "invalid")


class PortfolioMonitorLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_active_portfolio_is_retired_without_fetching_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_state_file = portfolio_monitor._STATE_FILE
            portfolio_monitor._STATE_FILE = Path(tmp) / "active_positions.json"
            try:
                state = portfolio_monitor._empty_state()
                state.update({
                    "target_week": "2020-01-06 ~ 2020-01-10",
                    "status": "active",
                    "positions": [{"code": "600000", "name": "过期自测"}],
                })
                portfolio_monitor._STATE_FILE.write_text(
                    json.dumps(state, ensure_ascii=False),
                    encoding="utf-8",
                )

                result = await portfolio_monitor.check_portfolio_stop()
                saved = json.loads(portfolio_monitor._STATE_FILE.read_text(encoding="utf-8"))

                self.assertEqual(result["status"], "expired")
                self.assertFalse(result["triggered_this_call"])
                self.assertEqual(saved["status"], "expired")
                self.assertIsNone(saved["stop_triggered_at"])
            finally:
                portfolio_monitor._STATE_FILE = original_state_file


class UniverseSnapshotTests(unittest.TestCase):
    def test_only_complete_live_batches_create_point_in_time_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_dir = eastmoney._UNIVERSE_CACHE_DIR
            eastmoney._UNIVERSE_CACHE_DIR = Path(tmp)
            try:
                complete = [{"code": f"{i:06d}", "name": f"样例{i}"} for i in range(95)]
                eastmoney._save_universe_cache(
                    "amount", complete, requested_limit=100, failed_pages=0
                )
                snapshots = list((Path(tmp) / "history").rglob("amount-*.json"))
                self.assertEqual(len(snapshots), 1)
                payload = json.loads(snapshots[0].read_text(encoding="utf-8"))
                self.assertTrue(payload["point_in_time_eligible"])
                self.assertEqual(payload["coverage_ratio"], 0.95)

                partial = [{"code": f"{i:06d}"} for i in range(50)]
                eastmoney._save_universe_cache(
                    "decline", partial, requested_limit=100, failed_pages=1
                )
                partial_snapshots = list((Path(tmp) / "history").rglob("decline-*.json"))
                self.assertEqual(partial_snapshots, [])
                fallback_cache = json.loads(
                    (Path(tmp) / "decline.json").read_text(encoding="utf-8")
                )
                self.assertEqual(fallback_cache["coverage_ratio"], 0.5)
                self.assertEqual(fallback_cache["failed_pages"], 1)
            finally:
                eastmoney._UNIVERSE_CACHE_DIR = original_dir


class MarketCodeMappingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.api = eastmoney.EastmoneyAPI()

    def test_explicit_index_suffix_and_bare_stock_are_not_confused(self) -> None:
        self.assertEqual(self.api._parse_secid("000001.SH"), "1.000001")
        self.assertEqual(self.api._parse_secid("399001.SZ"), "0.399001")
        self.assertEqual(self.api._parse_secid("000001"), "0.000001")
        self.assertEqual(self.api._parse_secid("sh.600000"), "1.600000")
        self.assertEqual(self.api._sina_symbol("000001.SH"), "sh000001")
        self.assertEqual(self.api._sina_symbol("000001"), "sz000001")

    async def test_index_quote_rejects_wrong_fallback_identity(self) -> None:
        self.api.get_stock_quote = AsyncMock(return_value={
            "code": "000001",
            "name": "平安银行",
            "price": 11.19,
        })
        self.assertIsNone(await self.api.get_index_quote("000001.SH"))

    async def test_index_quote_normalizes_verified_index(self) -> None:
        self.api.get_stock_quote = AsyncMock(return_value={
            "code": "000001",
            "name": "上证指数",
            "price": 3560.12,
            "change_pct": 0.5,
        })
        quote = await self.api.get_index_quote("000001.SH")
        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote["code"], "000001")
        self.assertEqual(quote["name"], "上证指数")
        self.assertTrue(quote["is_index"])


class ReportStoreTests(unittest.TestCase):
    def test_report_survives_restart_and_appends_audit_ledger(self) -> None:
        weights, cash = allocate_rank_weights(2)
        report = WeeklyReport(
            report_date="2026-08-09",
            target_week="2026-08-10 ~ 2026-08-14",
            market_summary="只概括候选数据。",
            recommendations=[
                _recommendation("600000", weights[0]),
                _recommendation("000001", weights[1]),
            ],
            total_candidates_scanned=5500,
            market_cap_eligible=800,
            kline_evaluated=790,
            scan_data_complete=True,
            scan_metrics_version="actual-v1",
            reversal_filtered=2,
            risk_warning="测试风险",
            strategy_notes="测试策略",
            strategy_version=STRATEGY.version,
            generated_at="2026-08-09T10:30:00",
            invested_position_pct=sum(weights),
            cash_position_pct=cash,
        )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first = save_weekly_report(report, base)
            second = save_weekly_report(report, base)
            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

            loaded = load_latest_report(base)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.strategy_version, STRATEGY.version)
            self.assertEqual(loaded.invested_position_pct, 60.0)
            self.assertEqual(loaded.cash_position_pct, 40.0)
            self.assertEqual(loaded.kline_evaluated, 790)
            self.assertTrue(loaded.scan_data_complete)
            self.assertEqual(loaded.scan_metrics_version, "actual-v1")

            lines = (base / "recommendation-ledger.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            record = json.loads(lines[-1])
            self.assertEqual(record["cash_position_pct"], 40.0)
            self.assertEqual(record["market_cap_eligible"], 800)
            self.assertEqual(record["kline_evaluated"], 790)
            self.assertEqual([item["position_pct"] for item in record["recommendations"]], [35.0, 25.0])


if __name__ == "__main__":
    unittest.main()
