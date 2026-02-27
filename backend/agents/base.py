"""
Agent 基类 - LLM 驱动版本
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import json
import logging

from models.agent_models import AgentSignal

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.last_analysis = None
        self.analysis_history = []
        self.is_running = False
        
    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        """
        执行分析，返回 {stock_code: AgentSignal} 的字典。
        每个 Agent 必须实现此方法。
        """
        pass
        
    def save_analysis(self, analysis: Dict[str, Any]):
        """保存分析结果"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "results": analysis,
        }
        self.last_analysis = record
        self.analysis_history.append(record)
        if len(self.analysis_history) > 100:
            self.analysis_history = self.analysis_history[-100:]
            
    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "name": self.name,
            "description": self.description,
            "is_running": self.is_running,
            "last_analysis_time": self.last_analysis.get("timestamp") if self.last_analysis else None,
            "analysis_count": len(self.analysis_history),
        }
        
    async def run_analysis(self, market_data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        """运行完整分析流程"""
        try:
            self.is_running = True
            results = await self.analyze(market_data)
            self.save_analysis({k: v.model_dump() for k, v in results.items()})
            return results
        except Exception as e:
            logger.error(f"Agent {self.name} analysis failed: {e}", exc_info=True)
            return {}
        finally:
            self.is_running = False


class AgentManager:
    """Agent 管理器"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.analysis_results: Dict[str, Dict[str, AgentSignal]] = {}
        
    def register_agent(self, agent: BaseAgent):
        """注册 Agent"""
        self.agents[agent.name] = agent
        
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取 Agent"""
        return self.agents.get(name)
        
    async def run_all_agents(
        self,
        market_data: Dict[str, Any],
        concurrency: int = 8,
    ) -> Dict[str, Dict[str, AgentSignal]]:
        """
        并发运行所有 Agent（asyncio.gather + Semaphore）。
        concurrency=8 表示最多同时 8 个 LLM 调用，避免触发 429。
        16 个 agent 原来串行约 240s，并发后预计 30-40s。
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _run_one(name: str, agent: "BaseAgent"):
            async with semaphore:
                logger.info(f"运行 Agent: {name}")
                try:
                    result = await agent.run_analysis(market_data)
                    return name, result
                except Exception as e:
                    logger.error(f"Agent {name} 失败: {e}")
                    return name, {}

        tasks = [_run_one(name, agent) for name, agent in self.agents.items()]
        pairs = await asyncio.gather(*tasks)
        agent_results = dict(pairs)
        self.analysis_results = agent_results
        return agent_results
        
    def get_all_signals(self) -> Dict[str, Dict[str, AgentSignal]]:
        """获取所有 Agent 的信号"""
        return self.analysis_results
        
    def get_agent_status(self) -> Dict[str, Any]:
        """获取所有 Agent 状态"""
        return {name: agent.get_status() for name, agent in self.agents.items()}


# 全局 Agent 管理器
agent_manager = AgentManager()
