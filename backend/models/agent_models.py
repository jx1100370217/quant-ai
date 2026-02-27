"""
Agent 统一输出模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Dict, List, Optional
import json


class AgentSignal(BaseModel):
    """每个分析 Agent 的统一输出"""
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(ge=0, le=100, description="置信度 0-100")
    reasoning: str = Field(description="分析推理说明")


class PortfolioDecision(BaseModel):
    """Portfolio Manager 对单只股票的决策"""
    action: Literal["buy", "sell", "hold"]
    quantity: int = Field(ge=0, description="交易股数")
    confidence: int = Field(ge=0, le=100, description="置信度 0-100")
    reasoning: str = Field(description="决策推理说明")


class BatchSignals(BaseModel):
    """批量分析输出：一次 LLM 调用分析所有股票，减少 API 调用次数"""
    signals: Dict[str, AgentSignal] = Field(description="股票代码到信号的映射")

    @field_validator("signals", mode="before")
    @classmethod
    def parse_signals_if_string(cls, v):
        """兼容 LLM 把 signals 值序列化为 JSON 字符串或格式异常的情况"""
        if isinstance(v, str):
            v = cls._try_parse_json(v)
        if not isinstance(v, dict):
            return {}
        # 确保每个 AgentSignal 值也能从字符串解析
        result = {}
        for k, val in v.items():
            if isinstance(val, str):
                parsed = cls._try_parse_json(val)
                if isinstance(parsed, dict):
                    result[k] = parsed
                # else skip unparseable signal
            else:
                result[k] = val
        return result

    @staticmethod
    def _try_parse_json(s: str):
        """尝试解析 JSON，修复常见的多余 } 问题"""
        if not isinstance(s, str):
            return s
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # 修复：末尾多余 } — 逐个剥离直到平衡
        cleaned = s.strip()
        for _ in range(5):  # 最多剥离5个
            if cleaned.count("{") == cleaned.count("}"):
                break
            if cleaned.endswith("}"):
                cleaned = cleaned[:-1].rstrip()
            else:
                break
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return s  # 无法解析，返回原始字符串


class PortfolioOutput(BaseModel):
    """Portfolio Manager 的完整输出"""
    decisions: Dict[str, PortfolioDecision] = Field(description="股票代码到决策的映射")

    @field_validator("decisions", mode="before")
    @classmethod
    def parse_decisions_if_string(cls, v):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                pass
        return v
