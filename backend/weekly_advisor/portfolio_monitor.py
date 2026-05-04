"""
组合级周内追踪止损监控 (V12b 运行期执行模块)
===================================================
背景：backtest_v12.py 验证了两道止损合作才能显著降低回撤 ——
  - 单股 -6% 硬止损（已通过 stop_loss_price 在下单时挂出）
  - 组合加权周内浮亏 ≤ -4% → 次日开盘全部平仓（本模块负责）

backtest 中的语义（compute_portfolio_ret）：
  · 每日收盘计算加权组合浮亏（单股触发 -6% 的贡献冻结在 -6%）
  · 一旦 port_ret ≤ -4%，触发"全部清仓"信号（最终按 -4% 结算）
  · 触发后不再重复检查，等下一周新周期

本模块在 live 场景复刻该语义：
  · save_active_positions   周报生成后记录买入价 + 权重
  · check_portfolio_stop    抓当前价 → 算加权浮亏 → 必要时触发清仓信号
  · 触发后 status 置为 stopped_out，并通过 Telegram 发一次警报

注意：本模块只产出"信号"（写状态 + 推送），不直接下单——
项目整体是推荐系统，交易动作由用户在券商端执行。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.eastmoney import eastmoney_api
from utils.telegram import send_telegram

from .models import WeeklyReport

logger = logging.getLogger(__name__)

# ── V12b 策略阈值（与 backtest_v12.py 保持一致）───────────────
SINGLE_STOP_PCT = -6.0       # 单股浮亏冻结阈值
PORTFOLIO_STOP_PCT = -4.0    # 组合浮亏触发阈值

# ── 状态文件位置 ───────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
_CACHE_DIR = _BASE / "cache"
_STATE_FILE = _CACHE_DIR / "active_positions.json"

# 写文件时的并发锁（读文件每次重新打开，不持锁）
_WRITE_LOCK = asyncio.Lock()


def _ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _empty_state() -> Dict[str, Any]:
    return {
        "target_week": "",
        "generated_at": "",
        "positions": [],
        "status": "inactive",          # inactive | active | stopped_out
        "stop_triggered_at": None,
        "last_checked": None,
        "last_portfolio_pnl_pct": None,
    }


def load_active_positions() -> Dict[str, Any]:
    """读取当前活跃持仓状态（无文件时返回空结构）"""
    if not _STATE_FILE.exists():
        return _empty_state()
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容旧结构
        for k, v in _empty_state().items():
            data.setdefault(k, v)
        return data
    except Exception as e:
        logger.warning(f"读取活跃持仓失败，返回空状态: {e}")
        return _empty_state()


async def _write_state(state: Dict[str, Any]) -> None:
    async with _WRITE_LOCK:
        _ensure_cache_dir()
        tmp = _STATE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _STATE_FILE)


async def save_active_positions(report: WeeklyReport) -> Dict[str, Any]:
    """
    周报生成后调用：把当期推荐锁定为活跃持仓

    - entry_price 用 report 里的 current_price（生成时的快照价）
    - weight_pct 用 report 的 position_pct（已按 V10_WEIGHTS 归一化）
    - 若已有同 target_week 的 stopped_out 状态，仍覆盖（新周期）
    """
    if not report.recommendations:
        # 没推荐就清空，避免遗留状态
        state = _empty_state()
        state["target_week"] = report.target_week
        state["generated_at"] = datetime.now().isoformat(timespec="seconds")
        await _write_state(state)
        logger.info("周报无推荐股，活跃持仓已清空")
        return state

    positions: List[Dict[str, Any]] = []
    for rec in report.recommendations:
        positions.append({
            "code": rec.code,
            "name": rec.name,
            "entry_price": float(rec.current_price),
            "weight_pct": float(rec.position_pct),
            "single_stop_price": float(rec.stop_loss_price),
            "target_price": float(rec.target_price),
            # 动态字段
            "last_price": None,
            "last_pnl_pct": None,
            "single_stopped": False,
        })

    state = {
        "target_week": report.target_week,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "positions": positions,
        "status": "active",
        "stop_triggered_at": None,
        "last_checked": None,
        "last_portfolio_pnl_pct": None,
    }
    await _write_state(state)
    logger.info(
        f"活跃持仓已保存: target_week={report.target_week} "
        f"positions={[(p['code'], p['weight_pct']) for p in positions]}"
    )
    return state


async def clear_active_positions() -> Dict[str, Any]:
    """手动清空（例如周五收盘后、或新周一开盘前）"""
    state = _empty_state()
    await _write_state(state)
    logger.info("活跃持仓已手动清空")
    return state


def _weight_sum(positions: List[Dict[str, Any]]) -> float:
    total = sum(float(p.get("weight_pct") or 0) for p in positions)
    return total if total > 0 else 100.0


def _compute_stock_pnl(entry: float, current: float) -> float:
    """单股浮亏 (%)；单股 ≤ -6% 的冻结在 _check_and_update 里做

    NOTE: 四舍五入到 4 位，避免浮点精度导致临界值（如 entry×0.94 产生 -5.9999964）
    漏掉 <= -6% 的比较；实际报价最多 4 位小数，这个精度对业务判定足够。
    """
    if entry <= 0:
        return 0.0
    return round((current - entry) / entry * 100.0, 4)


async def _notify_portfolio_stop(state: Dict[str, Any]) -> None:
    """组合止损首次触发时的 Telegram 警报"""
    try:
        lines = [
            "🚨 <b>V12b 组合止损触发</b>",
            f"🗓 目标周：{state['target_week']}",
            f"⏱ 触发时间：{state['stop_triggered_at']}",
            f"📉 组合加权浮亏：<b>{state['last_portfolio_pnl_pct']:+.2f}%</b> (阈值 {PORTFOLIO_STOP_PCT:+.1f}%)",
            "",
            "<b>建议操作：次日开盘全部清仓</b>",
            "",
            "<b>明细</b>",
        ]
        for p in state["positions"]:
            tag = " [单股止损]" if p.get("single_stopped") else ""
            lines.append(
                f"· {p['name']}（{p['code']}）: 买入 {p['entry_price']:.2f} → "
                f"现价 {(p.get('last_price') or 0):.2f} | "
                f"{(p.get('last_pnl_pct') or 0):+.2f}% × {p['weight_pct']:.0f}%{tag}"
            )
        await send_telegram("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.warning(f"组合止损 Telegram 推送失败: {e}")


async def check_portfolio_stop(force_notify: bool = False) -> Dict[str, Any]:
    """
    核心监控入口：抓当前价 → 算加权浮亏 → 必要时触发组合止损

    返回:
      {
        "status": "inactive" | "active" | "stopped_out",
        "triggered_this_call": bool,   # 本次调用是否触发（仅第一次触发为 True）
        "portfolio_pnl_pct": float,
        "target_week": str,
        "positions": [...],            # 含每只最新价和浮亏
        "message": str,
      }
    """
    state = load_active_positions()

    # 无活跃持仓，直接返回
    if state["status"] != "active" or not state["positions"]:
        return {
            "status": state["status"],
            "triggered_this_call": False,
            "portfolio_pnl_pct": state.get("last_portfolio_pnl_pct"),
            "target_week": state.get("target_week", ""),
            "positions": state.get("positions", []),
            "message": (
                "无活跃持仓（status=inactive）" if state["status"] == "inactive"
                else f"组合已触发止损（{state.get('stop_triggered_at')}），本周不再检查"
            ),
        }

    # 并发拉所有股票当前价
    async def _fetch(code: str) -> Optional[Dict[str, Any]]:
        try:
            return await eastmoney_api.get_stock_quote(code)
        except Exception as e:
            logger.warning(f"获取 {code} 行情失败: {e}")
            return None

    quotes = await asyncio.gather(
        *[_fetch(p["code"]) for p in state["positions"]],
        return_exceptions=False,
    )

    w_sum = _weight_sum(state["positions"])
    portfolio_pnl = 0.0
    fetched_count = 0

    for p, q in zip(state["positions"], quotes):
        if not q or not q.get("price"):
            # 抓不到价：跳过本只贡献，保持上次浮亏（更保守是按 0 算）
            continue

        current = float(q["price"])
        pnl = _compute_stock_pnl(float(p["entry_price"]), current)

        # 单股 -6% 冻结：一旦触发过，贡献永远按 -6% 算
        if p.get("single_stopped") or pnl <= SINGLE_STOP_PCT:
            p["single_stopped"] = True
            pnl = SINGLE_STOP_PCT

        p["last_price"] = round(current, 4)
        p["last_pnl_pct"] = round(pnl, 3)

        portfolio_pnl += (float(p["weight_pct"]) / w_sum) * pnl
        fetched_count += 1

    portfolio_pnl = round(portfolio_pnl, 3)
    now_iso = datetime.now().isoformat(timespec="seconds")
    state["last_checked"] = now_iso
    state["last_portfolio_pnl_pct"] = portfolio_pnl

    # 数据完全缺失时，不做触发判断，避免误报
    if fetched_count == 0:
        state["last_portfolio_pnl_pct"] = None
        await _write_state(state)
        logger.warning("所有持仓行情拉取失败，本轮跳过止损判断")
        return {
            "status": "active",
            "triggered_this_call": False,
            "portfolio_pnl_pct": None,
            "target_week": state["target_week"],
            "positions": state["positions"],
            "message": "行情全部缺失，本轮跳过",
        }

    triggered = portfolio_pnl <= PORTFOLIO_STOP_PCT

    if triggered:
        # 按 backtest 语义：最终结算按阈值封顶
        state["status"] = "stopped_out"
        state["stop_triggered_at"] = now_iso
        state["last_portfolio_pnl_pct"] = PORTFOLIO_STOP_PCT
        await _write_state(state)
        await _notify_portfolio_stop(state)
        logger.warning(
            f"🚨 组合止损触发! 周 {state['target_week']} 组合浮亏 {portfolio_pnl:+.2f}% "
            f"≤ {PORTFOLIO_STOP_PCT:+.1f}%"
        )
        return {
            "status": "stopped_out",
            "triggered_this_call": True,
            "portfolio_pnl_pct": portfolio_pnl,
            "target_week": state["target_week"],
            "positions": state["positions"],
            "message": f"组合浮亏 {portfolio_pnl:+.2f}% 触发止损，建议次日开盘清仓",
        }

    # 未触发：更新状态
    await _write_state(state)
    if force_notify:
        logger.info(
            f"组合浮亏检查: {portfolio_pnl:+.2f}% (阈值 {PORTFOLIO_STOP_PCT:+.1f}%) "
            f"| 持仓 {len(state['positions'])} 只 | 抓价成功 {fetched_count}"
        )
    return {
        "status": "active",
        "triggered_this_call": False,
        "portfolio_pnl_pct": portfolio_pnl,
        "target_week": state["target_week"],
        "positions": state["positions"],
        "message": f"组合浮亏 {portfolio_pnl:+.2f}% 安全",
    }
