"""
Telegram 推送通知工具
分析完成后，将结果格式化推送到指定 Telegram Chat

依赖：httpx（标准库 urllib 兜底），无需 aiohttp
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ── Agent 中文名映射 ────────────────────────────────────────
AGENT_DISPLAY = {
    # 量化支撑
    "TechnicalAnalyst":      "📐 技术分析师",
    "FundamentalAnalyst":    "📑 基本面分析师",
    "SentimentAnalyst":      "💬 情绪分析师",
    "RiskManager":           "🛡 风险管理师",
    # 价值派
    "WarrenBuffett":         "🎩 沃伦·巴菲特",
    "CharlieMunger":         "🦉 查理·芒格",
    "BenGraham":             "📖 本杰明·格雷厄姆",
    "MichaelBurry":          "🐻 迈克尔·伯里",
    "MohnishPabrai":         "🏛 莫尼什·帕伯莱",
    # 成长派
    "PeterLynch":            "🔍 彼得·林奇",
    "CathieWood":            "🚀 凯西·伍德",
    "PhilFisher":            "🌱 菲利普·费雪",
    "RakeshJhunjhunwala":    "🐂 拉克什·君君瓦拉",
    # 宏观/激进派
    "AswathDamodaran":       "🧮 阿斯沃斯·达摩达兰",
    "StanleyDruckenmiller":  "🌍 斯坦利·德鲁肯米勒",
    "BillAckman":            "⚡ 比尔·阿克曼",
}

SIGNAL_EMOJI = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}
ACTION_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡",
                "buy": "🟢", "sell": "🔴", "hold": "🟡"}


# ─────────────────────────────────────────────
# .env 直读（兼容 dotenv 未加载的场景）
# ─────────────────────────────────────────────

def _load_credentials() -> tuple[str, str]:
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        return token, chat_id

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key == "TELEGRAM_BOT_TOKEN":
                token = val
            elif key == "TELEGRAM_CHAT_ID":
                chat_id = val
    return token, chat_id


# ─────────────────────────────────────────────
# 核心发送（httpx 优先，urllib 兜底）
# ─────────────────────────────────────────────

async def send_telegram(text: str, parse_mode: str = "HTML") -> bool:
    token, chat_id = _load_credentials()
    if not token or not chat_id:
        logger.warning("Telegram 未配置（TOKEN 或 CHAT_ID 为空），跳过推送")
        return False

    # 截断至 Telegram 4096 字符上限
    if len(text) > 4096:
        text = text[:4090] + "\n…"

    url     = TELEGRAM_API.format(token=token)
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

    # ── httpx 异步 ──
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram 推送成功 (httpx)")
                return True
            else:
                logger.warning(f"Telegram 推送失败 [{resp.status_code}]: {resp.text}")
                return False
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Telegram httpx 异常: {e}")
        return False

    # ── urllib 同步兜底 ──
    try:
        import json, urllib.request
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(url, data=data,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info("Telegram 推送成功 (urllib)")
                return True
            logger.warning(f"Telegram 推送失败 [{resp.status}]")
            return False
    except Exception as e:
        logger.error(f"Telegram urllib 异常: {e}")
        return False


async def send_messages(messages: List[str]) -> None:
    """顺序发送多条消息"""
    import asyncio
    for msg in messages:
        if msg.strip():
            await send_telegram(msg)
            await asyncio.sleep(0.3)  # 避免触发 Telegram 频率限制


# ─────────────────────────────────────────────
# 公共：生成单股大师详情块
# ─────────────────────────────────────────────

def _stock_stats(agent_signals: Dict[str, Any]) -> tuple:
    """返回 (bullish, bearish, neutral, avg_confidence, dominant_signal)"""
    bullish = bearish = neutral = 0
    total_conf = 0
    n = 0
    for sig in agent_signals.values():
        s = sig.get("signal", "neutral") if isinstance(sig, dict) else "neutral"
        c = sig.get("confidence", 0)     if isinstance(sig, dict) else 0
        if s == "bullish":   bullish += 1
        elif s == "bearish": bearish += 1
        else:                neutral += 1
        total_conf += c
        n += 1
    avg_c = round(total_conf / n, 1) if n else 0
    dominant = "bullish" if bullish >= bearish else ("bearish" if bearish > neutral else "neutral")
    return bullish, bearish, neutral, avg_c, dominant


def _compact_master_line(agent_signals: Dict[str, Any]) -> str:
    """生成紧凑的大师信号行，如：🟢巴菲特 🔴伯里 🟡芒格 ..."""
    # 短名映射
    SHORT_NAME = {
        "TechnicalAnalyst": "技术", "FundamentalAnalyst": "基本面",
        "SentimentAnalyst": "情绪", "RiskManager": "风控",
        "WarrenBuffett": "巴菲特", "CharlieMunger": "芒格",
        "BenGraham": "格雷厄姆", "MichaelBurry": "伯里",
        "MohnishPabrai": "帕伯莱", "PeterLynch": "林奇",
        "CathieWood": "伍德", "PhilFisher": "费雪",
        "RakeshJhunjhunwala": "君君瓦拉", "AswathDamodaran": "达摩达兰",
        "StanleyDruckenmiller": "德鲁肯", "BillAckman": "阿克曼",
    }
    parts = []
    for agent_name in AGENT_DISPLAY:
        sig = agent_signals.get(agent_name)
        if not sig:
            continue
        s = sig.get("signal", "neutral") if isinstance(sig, dict) else "neutral"
        emoji = SIGNAL_EMOJI.get(s, "⚪")
        short = SHORT_NAME.get(agent_name, agent_name)
        parts.append(f"{emoji}{short}")
    return " ".join(parts)


def _master_detail_block(
    code: str,
    name: str,
    agent_signals: Dict[str, Any],
    ts: str = "",
    header_extra: str = "",
) -> str:
    """
    为单只股票生成包含全部大师分析的消息块。
    agent_signals: { agent_name: { signal, confidence, reasoning } }
    """
    bullish, bearish, neutral, avg_c, dominant = _stock_stats(agent_signals)

    lines = [
        f"{SIGNAL_EMOJI.get(dominant,'⚪')} <b>{name}（{code}）</b>{header_extra}",
        f"看多 {bullish} | 看空 {bearish} | 中性 {neutral}   平均置信度 {avg_c:.1f}%",
    ]
    if ts:
        lines.insert(0, f"🕐 {ts}")
    lines.append("")

    # 按分组顺序列出所有大师
    for agent_name, display in AGENT_DISPLAY.items():
        sig = agent_signals.get(agent_name)
        if not sig:
            continue
        s = sig.get("signal", "neutral") if isinstance(sig, dict) else "neutral"
        c = sig.get("confidence", 0)     if isinstance(sig, dict) else 0
        r = sig.get("reasoning", "")     if isinstance(sig, dict) else ""
        emoji = SIGNAL_EMOJI.get(s, "⚪")
        lines.append(f"{emoji} <b>{display}</b>  {c}%")
        if r:
            # 每条推理截断到 100 字
            lines.append(f"   <i>{str(r)[:100]}</i>")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 格式化：全量分析结果
# ─────────────────────────────────────────────

def format_full_analysis(result: Dict[str, Any]) -> List[str]:
    """
    /api/analysis/run 推送 — 合并为单条消息
    """
    decisions:    Dict[str, Any] = result.get("portfolio_decisions", {})
    agent_signals_all: Dict[str, Any] = result.get("agent_signals", {})
    ts = result.get("timestamp", "")[:16].replace("T", " ")

    lines = [
        "📊 <b>QuantAI · 全量分析完成</b>",
        f"🕐 {ts}",
        "",
    ]
    if not decisions:
        lines.append("⚠️ 暂无决策结果")
        return ["\n".join(lines)]

    # 转置 agent_signals
    per_stock: Dict[str, Dict[str, Any]] = {}
    for agent_name, signals in agent_signals_all.items():
        for code, sig in signals.items():
            per_stock.setdefault(code, {})[agent_name] = sig

    # 每只股票：决策 + 统计 + 紧凑大师信号
    for code, d in decisions.items():
        action = d.get("action", "hold")
        conf   = d.get("confidence", 0)
        reason = d.get("reasoning", d.get("reason", ""))
        emoji  = ACTION_EMOJI.get(action, "⚪")
        agent_sigs = per_stock.get(code, {})
        b, br, neu, avg_c, dominant = _stock_stats(agent_sigs)

        lines.append(f"{emoji} <b>{code}</b>  {action.upper()} {conf}%  "
                      f"(多{b}/空{br}/中{neu} 置信{avg_c:.0f}%)")
        if reason:
            lines.append(f"   📝 <i>{str(reason)[:120]}</i>")
        if agent_sigs:
            lines.append(f"   {_compact_master_line(agent_sigs)}")
        lines.append("")

    text = "\n".join(lines).strip()
    # 如果超过 4000 字符，拆分为多条
    if len(text) <= 4000:
        return [text]
    return [text[:4000] + "\n…"]


# ─────────────────────────────────────────────
# 格式化：选股推荐结果
# ─────────────────────────────────────────────

def format_market_picks(result: Dict[str, Any]) -> List[str]:
    """
    /api/agents/market-picks 推送 — 合并为单条消息
    """
    ts          = result.get("timestamp", "")[:16].replace("T", " ")
    sector_name = result.get("sector_name", "")
    cnt         = result.get("candidates_count", 0)
    sector_pick = result.get("sector_pick", {})
    master_pick = result.get("master_pick", {})

    def _pick_block(label: str, emoji: str, pick: dict) -> list:
        if not pick:
            return [f"{emoji} {label}：无"]
        n    = pick.get("name", "")
        code = pick.get("code", "")
        b    = pick.get("bullish", 0)
        brr  = pick.get("bearish", 0)
        neu  = pick.get("neutral", 0)
        ac   = pick.get("avg_confidence", 0)
        pr   = pick.get("price", 0)
        ch   = pick.get("change_pct", 0)
        arr  = "▲" if ch >= 0 else "▼"
        lines = [
            f"{emoji} <b>{label}：{n}（{code}）</b>  {pr:.2f} {arr}{abs(ch):.2f}%",
            f"   多{b}/空{brr}/中{neu}  置信{ac:.0f}%",
        ]
        sigs = pick.get("agent_signals", {})
        if sigs:
            lines.append(f"   {_compact_master_line(sigs)}")
        return lines

    lines = [
        "🔍 <b>QuantAI · 选股推荐完成</b>",
        f"🕐 {ts}   候选 {cnt} 只   板块：{sector_name}",
        "",
    ]
    lines.extend(_pick_block("板块精选", "🏆", sector_pick))
    lines.append("")
    lines.extend(_pick_block("大师精选", "🌟", master_pick))

    return ["\n".join(lines)]


# ─────────────────────────────────────────────
# 格式化：持仓分析结果
# ─────────────────────────────────────────────

def format_holdings_analysis(result: Dict[str, Any], holdings: list) -> List[str]:
    """
    /api/agents/analyze-holdings 推送 — 合并为单条消息
    """
    ts          = result.get("timestamp", "")[:16].replace("T", " ")
    data        = result.get("data", {})
    agent_count = result.get("agent_count", len(data))
    stock_count = result.get("stock_count", 0)

    # 转置：{ stock_code: { agent_name: {signal,conf,reasoning} } }
    per_stock: Dict[str, Dict[str, Any]] = {}
    for agent_name, signals in data.items():
        for code, sig in signals.items():
            per_stock.setdefault(code, {})[agent_name] = sig

    name_map = {h.get("code", ""): h.get("name", h.get("code", "")) for h in holdings}

    lines = [
        "📋 <b>QuantAI · 持仓分析完成</b>",
        f"🕐 {ts}   {stock_count} 只股票 × {agent_count} 位大师",
        "",
    ]

    for code, agent_sigs in per_stock.items():
        b, brr, neu, avg_c, dominant = _stock_stats(agent_sigs)
        nm = name_map.get(code, code)
        lines.append(
            f"{SIGNAL_EMOJI.get(dominant,'⚪')} <b>{nm}（{code}）</b>"
            f"  多{b}/空{brr}/中{neu}  置信{avg_c:.0f}%"
        )
        lines.append(f"   {_compact_master_line(agent_sigs)}")
        lines.append("")

    text = "\n".join(lines).strip()
    if len(text) <= 4000:
        return [text]
    return [text[:4000] + "\n…"]


# ─────────────────────────────────────────────
# 便捷入口
# ─────────────────────────────────────────────

async def notify_full_analysis(result: Dict[str, Any]) -> None:
    msgs = format_full_analysis(result)
    await send_messages(msgs)


async def notify_market_picks(result: Dict[str, Any]) -> None:
    msgs = format_market_picks(result)
    await send_messages(msgs)


async def notify_holdings_analysis(result: Dict[str, Any], holdings: list) -> None:
    msgs = format_holdings_analysis(result, holdings)
    await send_messages(msgs)
