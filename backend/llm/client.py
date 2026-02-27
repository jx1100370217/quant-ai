"""
LLM Client - 封装 Anthropic SDK 调用，支持 Pydantic 结构化输出

支持认证方式：
- ANTHROPIC_API_KEY: 标准 API key
- ANTHROPIC_OAUTH_TOKEN: Claude Code Max OAuth token（通过 OpenClaw，需要特殊 headers）
"""
import asyncio
import json
import time
import threading
import logging
import os
from typing import Type, TypeVar, Optional, Callable
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

# 确保 .env 在任何 LLM 调用前加载（兼容直接 import client 的场景）
load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-4-6"

# Claude Code Max OAuth 需要此 system prompt 前缀
_CLAUDE_CODE_PREFIX = "You are Claude Code, Anthropic's official CLI for Claude."

# 全局信号量：限制并发 LLM 调用数量（避免 429）
# asyncio.to_thread 真正并发后，需要控制实际并发数
_LLM_SEMAPHORE = threading.Semaphore(4)

# 全局限速锁：LLM 调用间最小间隔
_LAST_CALL_TIME = 0.0
_RATE_LOCK = threading.Lock()
_MIN_INTERVAL = 0.3  # 真正并发后可以更激进（线程池 + semaphore 已限流）


def _rate_limit_wait():
    """确保 LLM 调用之间有最小间隔"""
    global _LAST_CALL_TIME
    with _RATE_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL_TIME
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _LAST_CALL_TIME = time.time()


def _create_client() -> anthropic.Anthropic:
    """创建 Anthropic client，自动检测认证方式"""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    oauth_token = os.environ.get("ANTHROPIC_OAUTH_TOKEN", "").strip()

    if api_key:
        return anthropic.Anthropic(api_key=api_key)
    elif oauth_token:
        return anthropic.Anthropic(
            api_key=None,
            auth_token=oauth_token,
            default_headers={
                "accept": "application/json",
                "anthropic-dangerous-direct-browser-access": "true",
                "anthropic-beta": "claude-code-20250219,oauth-2025-04-20",
                "user-agent": "claude-cli/2.1.2 (external, cli)",
                "x-app": "cli",
            },
        )
    else:
        raise RuntimeError(
            "未找到 Anthropic 认证配置。请设置 ANTHROPIC_API_KEY 或 ANTHROPIC_OAUTH_TOKEN。"
        )


def _is_oauth_mode() -> bool:
    import os
    return bool(os.environ.get("ANTHROPIC_OAUTH_TOKEN", "").strip()) and \
           not bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _build_system_prompt(system_prompt: str):
    """OAuth 模式必须以 Claude Code 前缀开头"""
    if _is_oauth_mode():
        parts = [{"type": "text", "text": _CLAUDE_CODE_PREFIX}]
        if system_prompt:
            parts.append({"type": "text", "text": system_prompt})
        return parts
    return system_prompt or None


def call_llm(
    prompt: str,
    pydantic_model: Type[T],
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
    default_factory: Optional[Callable[[], T]] = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> T:
    """
    调用 Anthropic LLM，返回 Pydantic 结构化输出（tool_use 模式）。
    内置全局信号量防止并发超限，智能 429 退避。
    """
    tool_name = f"output_{pydantic_model.__name__.lower()}"
    tool_schema = _clean_json_schema(pydantic_model.model_json_schema())
    tool = {
        "name": tool_name,
        "description": f"Output structured {pydantic_model.__name__} data",
        "input_schema": tool_schema,
    }
    messages = [{"role": "user", "content": prompt}]
    system = _build_system_prompt(system_prompt)

    for attempt in range(max_retries):
        with _LLM_SEMAPHORE:
            _rate_limit_wait()
            try:
                client = _create_client()
                kwargs = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                    "tools": [tool],
                    "tool_choice": {"type": "tool", "name": tool_name},
                }
                if system:
                    kwargs["system"] = system

                response = client.messages.create(**kwargs)

                for block in response.content:
                    if block.type == "tool_use" and block.name == tool_name:
                        return pydantic_model.model_validate(block.input)

                # fallback: 从 text 解析
                for block in response.content:
                    if block.type == "text":
                        return _parse_json_from_text(block.text, pydantic_model)

                logger.warning(f"LLM 未返回结构化输出 (attempt {attempt + 1})")

            except anthropic.RateLimitError as e:
                # 429: 指数退避，但上限 15s（原30s太激进，16个agent叠加会超时）
                wait = min(5 * (attempt + 1), 15)   # 5s, 10s, 15s
                logger.warning(f"Rate limit 429，等待 {wait}s 后重试... ({attempt+1}/{max_retries})")
                time.sleep(wait)

            except anthropic.APIError as e:
                logger.error(f"API 错误 (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    break
                time.sleep(5)

            except Exception as e:
                logger.error(f"LLM 调用异常 (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    break
                time.sleep(2)

    if default_factory:
        logger.warning(f"LLM 全部重试失败，返回默认值 ({pydantic_model.__name__})")
        return default_factory()

    raise RuntimeError(f"LLM 调用失败，已重试 {max_retries} 次")


def call_llm_text(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    """调用 LLM 返回纯文本"""
    messages = [{"role": "user", "content": prompt}]
    system = _build_system_prompt(system_prompt)

    for attempt in range(max_retries):
        with _LLM_SEMAPHORE:
            _rate_limit_wait()
            try:
                client = _create_client()
                kwargs = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                }
                if system:
                    kwargs["system"] = system

                response = client.messages.create(**kwargs)
                for block in response.content:
                    if block.type == "text":
                        return block.text
                return ""

            except anthropic.RateLimitError:
                wait = 30 * (attempt + 1)
                logger.warning(f"Rate limit 429，等待 {wait}s")
                time.sleep(wait)
            except Exception as e:
                logger.error(f"call_llm_text 错误: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(3)

    return ""


# ──────────────────────────────────────────────
# 内部工具函数
# ──────────────────────────────────────────────

def _parse_json_from_text(text: str, model_class: Type[T]) -> T:
    text = text.strip()
    if "```json" in text:
        s = text.index("```json") + 7
        e = text.index("```", s)
        text = text[s:e].strip()
    elif "```" in text:
        s = text.index("```") + 3
        e = text.index("```", s)
        text = text[s:e].strip()
    if not text.startswith("{"):
        bs = text.find("{")
        if bs != -1:
            text = text[bs: text.rfind("}") + 1]
    return model_class.model_validate(json.loads(text))


def _clean_json_schema(schema: dict) -> dict:
    defs = schema.pop("$defs", None) or schema.pop("definitions", None)
    if defs:
        schema = _resolve_refs(schema, defs)
    for key in ["title", "description", "$schema"]:
        schema.pop(key, None)
    return schema


def _resolve_refs(obj, defs):
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref_name = obj["$ref"].split("/")[-1]
            if ref_name in defs:
                resolved = _resolve_refs(defs[ref_name].copy(), defs)
                resolved.pop("title", None)
                return resolved
            return obj
        return {k: _resolve_refs(v, defs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(i, defs) for i in obj]
    return obj


# ── 异步包装：在线程池中执行同步 LLM 调用，不阻塞事件循环 ──────────
async def acall_llm(
    prompt: str,
    pydantic_model: Type[T],
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
    default_factory: Optional[Callable[[], T]] = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> T:
    """call_llm 的异步版本，通过 asyncio.to_thread 在线程池中执行"""
    return await asyncio.to_thread(
        call_llm,
        prompt=prompt,
        pydantic_model=pydantic_model,
        system_prompt=system_prompt,
        model=model,
        max_retries=max_retries,
        default_factory=default_factory,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def acall_llm_text(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    """call_llm_text 的异步版本"""
    return await asyncio.to_thread(
        call_llm_text,
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        max_retries=max_retries,
        temperature=temperature,
        max_tokens=max_tokens,
    )
