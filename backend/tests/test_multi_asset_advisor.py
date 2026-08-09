from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from weekly_advisor.asset_models import (
    CryptoRecommendation,
    CryptoWeeklyReport,
    FundRecommendation,
    FundWeeklyReport,
)
from weekly_advisor.asset_report_store import load_latest_asset_report, save_asset_report
from weekly_advisor.crypto_advisor import parse_binance_klines, score_crypto_candidate
from weekly_advisor.fund_advisor import _diversified_top, _fetch_fund_history, score_fund_candidate


def _fund_history(values: list[float]) -> list[dict]:
    return [
        {
            "date": f"2026-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}",
            "nav": value,
            "cumulative_nav": value,
            "subscribe_status": "开放申购",
            "redeem_status": "开放赎回",
        }
        for index, value in enumerate(values)
    ]


def _crypto_candles(values: list[float]) -> list[dict]:
    return [
        {"time": index + 1, "close": value, "volume": 1_000_000 * (1 + index / 1000)}
        for index, value in enumerate(values)
    ]


class FundStrategyTests(unittest.TestCase):
    def test_specific_fund_uptrend_is_eligible(self) -> None:
        result = score_fund_candidate(
            {"code": "021528", "name": "财通成长优选混合C", "fund_type": "混合型-灵活"},
            _fund_history([1 + index * 0.008 for index in range(90)]),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["eligible"])
        self.assertEqual(result["code"], "021528")
        self.assertGreater(result["potential_score"], 55)
        self.assertGreater(result["upside_potential_pct"], 0)
        self.assertEqual(result["subscribe_status"], "开放申购")

    def test_downtrend_or_closed_subscription_is_not_eligible(self) -> None:
        history = _fund_history([2 - index * 0.008 for index in range(90)])
        history[-1]["subscribe_status"] = "暂停申购"
        result = score_fund_candidate(
            {"code": "000001", "name": "测试成长混合C", "fund_type": "混合型-偏股"},
            history,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result["eligible"])

    def test_insufficient_fund_history_is_rejected(self) -> None:
        result = score_fund_candidate(
            {"code": "021528", "name": "财通成长优选混合C", "fund_type": "混合型-灵活"},
            _fund_history([1 + index * 0.01 for index in range(40)]),
        )
        self.assertIsNone(result)

    def test_strategy_group_concentration_is_limited(self) -> None:
        candidates = [
            {"strategy_group": "科技成长", "potential_score": 90 - index}
            for index in range(4)
        ] + [{"strategy_group": "医药健康", "potential_score": 70}]
        selected = _diversified_top(candidates, limit=5)
        self.assertEqual(sum(item["strategy_group"] == "科技成长" for item in selected), 2)
        self.assertEqual(len(selected), 3)


class FundHistoryFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_api_is_paginated_past_twenty_row_cap(self) -> None:
        class FakeResponse:
            def __init__(self, rows: list[dict]) -> None:
                self.status = 200
                self._rows = rows

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args) -> None:
                return None

            async def json(self, content_type=None) -> dict:
                return {"Data": {"LSJZList": self._rows}}

        class FakeSession:
            def __init__(self) -> None:
                self.pages: list[int] = []

            def get(self, _url, params, headers) -> FakeResponse:
                page = int(params["pageIndex"])
                self.pages.append(page)
                rows = [
                    {
                        "FSRQ": f"2026-P{page}-{index:02d}",
                        "DWJZ": "1.1000",
                        "LJJZ": "1.1000",
                        "SGZT": "开放申购",
                        "SHZT": "开放赎回",
                    }
                    for index in range(20)
                ]
                return FakeResponse(rows)

        session = FakeSession()
        cache: dict = {}
        history = await _fetch_fund_history(
            session,  # type: ignore[arg-type]
            {"code": "021528", "name": "财通成长优选混合C", "fund_type": "混合型-灵活"},
            cache,
            force=True,
        )
        self.assertIsNotNone(history)
        self.assertEqual(len(history or []), 100)
        self.assertEqual(session.pages, [1, 2, 3, 4, 5])
        self.assertIn("021528", cache)


class CryptoStrategyTests(unittest.TestCase):
    def test_binance_schema_uses_close_at_index_four(self) -> None:
        payload = [[1_700_000_000_000, "90", "110", "80", "105", "12.5", 1_700_086_399_999]]
        candles = parse_binance_klines(payload)
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["open"], 90.0)
        self.assertEqual(candles[0]["close"], 105.0)

    def test_positive_crypto_trend_can_be_recommended(self) -> None:
        result = score_crypto_candidate(
            {"symbol": "SOLUSDT", "name": "Solana", "category": "高性能公链"},
            _crypto_candles([40 + index * 0.6 for index in range(90)]),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["eligible"])
        self.assertGreater(result["potential_score"], 55)
        self.assertGreater(result["upside_potential_pct"], 0)

    def test_negative_crypto_trend_is_not_recommended(self) -> None:
        result = score_crypto_candidate(
            {"symbol": "ETHUSDT", "name": "Ethereum", "category": "智能合约"},
            _crypto_candles([100 - index * 0.5 for index in range(90)]),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result["eligible"])

    def test_insufficient_crypto_history_is_rejected(self) -> None:
        result = score_crypto_candidate(
            {"symbol": "BTCUSDT", "name": "Bitcoin", "category": "价值储存"},
            _crypto_candles([50_000 for _ in range(30)]),
        )
        self.assertIsNone(result)


class AssetReportStoreTests(unittest.TestCase):
    def test_fund_and_crypto_reports_use_separate_stores(self) -> None:
        fund = FundRecommendation(
            code="021528", name="财通成长优选混合C", fund_type="混合型-灵活",
            strategy_group="均衡成长", nav=4.346, nav_date="2026-08-07",
            position_pct=25, potential_score=75, upside_potential_pct=5,
            return_1w=10, return_1m=20, return_3m=30, volatility_3m=35,
            max_drawdown_3m=-12, positive_week_ratio=70, subscribe_status="开放申购",
            redeem_status="开放赎回", reason="测试", risk_note="测试",
        )
        fund_report = FundWeeklyReport(
            report_date="2026-08-09", target_week="2026-08-10 ~ 2026-08-14",
            market_summary="测试", recommendations=[fund], universe_size=34,
            funds_evaluated=30, eligible_count=5, invested_position_pct=25,
            cash_position_pct=75, risk_warning="测试", strategy_notes="测试",
            data_source="测试源", generated_at="2026-08-09T10:00:00",
        )
        coin = CryptoRecommendation(
            symbol="SOL-USDT", name="Solana", category="高性能公链", current_price=100,
            position_pct=35, potential_score=80, upside_potential_pct=12,
            return_7d=10, return_30d=25, ma20_gap=8, ma60_gap=15,
            volume_ratio_7d=1.2, volatility_20d=70, max_drawdown_30d=-15,
            risk_line_price=90, reason="测试", risk_note="测试",
        )
        crypto_report = CryptoWeeklyReport(
            report_date="2026-08-09", target_week="2026-08-10 ~ 2026-08-16",
            market_summary="测试", recommendations=[coin], universe_size=16,
            assets_evaluated=16, eligible_count=4, invested_position_pct=35,
            cash_position_pct=65, risk_warning="测试", strategy_notes="测试",
            data_source="测试源", data_updated_at=datetime.now(timezone.utc).isoformat(),
            generated_at="2026-08-09T10:00:00",
        )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            save_asset_report(fund_report, "fund", base)
            save_asset_report(crypto_report, "crypto", base)
            loaded_fund = load_latest_asset_report(FundWeeklyReport, "fund", base)
            loaded_crypto = load_latest_asset_report(CryptoWeeklyReport, "crypto", base)
            self.assertIsNotNone(loaded_fund)
            self.assertIsNotNone(loaded_crypto)
            assert loaded_fund is not None and loaded_crypto is not None
            self.assertEqual(loaded_fund.recommendations[0].name, "财通成长优选混合C")
            self.assertEqual(loaded_crypto.recommendations[0].symbol, "SOL-USDT")
            self.assertTrue((base / "fund" / "recommendation-ledger.jsonl").exists())
            self.assertTrue((base / "crypto" / "recommendation-ledger.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
