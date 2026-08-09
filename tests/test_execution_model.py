from __future__ import annotations

import unittest
from datetime import date

import numpy as np

from scripts.execution_model import (
    ExecutionConfig,
    is_intraday_sellable,
    is_open_buyable,
    is_open_sellable,
    net_trade_return_pct,
    price_limit_pct,
    stamp_duty_bps,
)


ZERO_COST = ExecutionConfig(
    commission_bps=0.0,
    slippage_bps=0.0,
    stamp_duty_bps_before_20230828=0.0,
    stamp_duty_bps_after_20230828=0.0,
)


class ExecutionRuleTests(unittest.TestCase):
    def test_board_specific_price_limits(self) -> None:
        self.assertEqual(price_limit_pct("sh.600000", "浦发银行"), 0.10)
        self.assertEqual(price_limit_pct("sz.300001", "特锐德"), 0.20)
        self.assertEqual(price_limit_pct("sh.688001", "华兴源创"), 0.20)
        self.assertEqual(price_limit_pct("bj.830000", "北交样例"), 0.30)
        self.assertEqual(price_limit_pct("600000", "ST样例"), 0.05)

    def test_limit_up_open_is_not_assumed_buyable(self) -> None:
        self.assertFalse(is_open_buyable(11.0, 11.0, 11.0, 1000, 10.0, "600000"))
        self.assertTrue(is_open_buyable(10.5, 10.8, 10.4, 1000, 10.0, "600000"))

    def test_limit_down_and_suspension_delay_exit(self) -> None:
        self.assertFalse(is_open_sellable(9.0, 9.0, 9.0, 1000, 10.0, "600000"))
        self.assertFalse(is_intraday_sellable(9.0, 9.0, 9.0, 1000, 10.0, "600000"))
        self.assertTrue(is_intraday_sellable(9.0, 9.3, 9.0, 1000, 10.0, "600000"))
        self.assertFalse(is_open_sellable(10.0, 10.0, 10.0, 0, 10.0, "600000"))

    def test_costs_and_stamp_duty_reduce_return(self) -> None:
        config = ExecutionConfig(commission_bps=3, slippage_bps=10)
        gross = net_trade_return_pct(10.0, 11.0, date(2024, 1, 2), date(2024, 1, 5), ZERO_COST)
        net = net_trade_return_pct(10.0, 11.0, date(2024, 1, 2), date(2024, 1, 5), config)
        self.assertAlmostEqual(gross, 10.0, places=8)
        self.assertLess(net, gross)
        self.assertEqual(stamp_duty_bps(date(2023, 8, 27), config), 10.0)
        self.assertEqual(stamp_duty_bps(date(2023, 8, 28), config), 5.0)


class PortfolioExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from scripts import backtest_engine

        cls.engine = backtest_engine

    def _install_market(self, dates, opens, highs, lows, closes, volumes) -> None:
        self.original_dates = self.engine.DATES
        self.original_didx = self.engine.DIDX
        self.original_a = self.engine.A
        self.engine.DATES = dates
        self.engine.DIDX = {d: i for i, d in enumerate(dates)}
        self.engine.A = {
            "sh.600000": {
                "name": "执行自测",
                "o": np.array(opens, float),
                "h": np.array(highs, float),
                "l": np.array(lows, float),
                "c": np.array(closes, float),
                "v": np.array(volumes, float),
                "pos": {d: i for i, d in enumerate(dates)},
            }
        }

    def tearDown(self) -> None:
        if hasattr(self, "original_dates"):
            self.engine.DATES = self.original_dates
            self.engine.DIDX = self.original_didx
            self.engine.A = self.original_a

    def test_buy_day_stop_exits_next_day_under_t_plus_one(self) -> None:
        dates = ["2026-07-31", "2026-08-03", "2026-08-04", "2026-08-07"]
        self._install_market(
            dates,
            opens=[10, 10, 9.0, 9.1], highs=[10, 10.2, 9.2, 9.2],
            lows=[10, 9.3, 8.9, 9.0], closes=[10, 9.5, 9.1, 9.1],
            volumes=[1000, 1000, 1000, 1000],
        )
        result = self.engine._port(
            [("sh.600000", 50)], "2026-08-03", "2026-08-07", [0.35],
            execution_config=ZERO_COST,
        )
        self.assertAlmostEqual(result["picks"][0], -10.0, places=6)
        self.assertAlmostEqual(result["ret"], -3.5, places=6)

    def test_friday_portfolio_stop_exits_next_week_open(self) -> None:
        dates = [
            "2026-07-31", "2026-08-03", "2026-08-04", "2026-08-05",
            "2026-08-06", "2026-08-07", "2026-08-10",
        ]
        self._install_market(
            dates,
            opens=[10, 10, 10, 10, 10, 9.8, 9.2],
            highs=[10, 10.1, 10.1, 10.1, 10.1, 9.9, 9.3],
            lows=[10, 9.9, 9.9, 9.9, 9.9, 9.5, 9.1],
            closes=[10, 10, 10, 10, 10, 9.5, 9.2],
            volumes=[1000] * len(dates),
        )
        result = self.engine._port(
            [("sh.600000", 50)], "2026-08-03", "2026-08-07", [1.0],
            execution_config=ZERO_COST,
        )
        self.assertTrue(result["portfolio_stopped"])
        self.assertAlmostEqual(result["picks"][0], -8.0, places=6)

    def test_limit_up_entry_remains_cash(self) -> None:
        dates = ["2026-07-31", "2026-08-03", "2026-08-07"]
        self._install_market(
            dates,
            opens=[10, 11, 11], highs=[10, 11, 11], lows=[10, 11, 11],
            closes=[10, 11, 11], volumes=[1000, 1000, 1000],
        )
        result = self.engine._port(
            [("sh.600000", 50)], "2026-08-03", "2026-08-07", [0.35],
            execution_config=ZERO_COST,
        )
        self.assertEqual(result["executed_count"], 0)
        self.assertEqual(result["unfilled_entries"], 1)
        self.assertEqual(result["ret"], 0.0)


if __name__ == "__main__":
    unittest.main()
