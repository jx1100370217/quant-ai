from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import json

class BaseAgent(ABC):
    """Agent基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.last_analysis = None
        self.analysis_history = []
        self.is_running = False
        
    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析，返回分析结果"""
        pass
        
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """根据分析结果生成交易信号"""
        return {
            "signal": "HOLD",  # BUY, SELL, HOLD
            "confidence": 0.5,  # 0-1
            "reason": "默认持有",
            "timestamp": datetime.now().isoformat()
        }
        
    def save_analysis(self, analysis: Dict[str, Any]):
        """保存分析结果"""
        analysis["timestamp"] = datetime.now().isoformat()
        analysis["agent"] = self.name
        self.last_analysis = analysis
        self.analysis_history.append(analysis)
        
        # 只保留最近100条记录
        if len(self.analysis_history) > 100:
            self.analysis_history = self.analysis_history[-100:]
            
    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "name": self.name,
            "description": self.description,
            "is_running": self.is_running,
            "last_analysis_time": self.last_analysis.get("timestamp") if self.last_analysis else None,
            "analysis_count": len(self.analysis_history)
        }
        
    async def run_analysis(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行完整的分析流程"""
        try:
            self.is_running = True
            
            # 执行分析
            analysis = await self.analyze(market_data)
            
            # 生成信号
            signal = await self.get_signal(analysis)
            
            # 合并结果
            result = {
                **analysis,
                "signal": signal,
                "agent": self.name,
                "timestamp": datetime.now().isoformat()
            }
            
            # 保存结果
            self.save_analysis(result)
            
            return result
            
        except Exception as e:
            error_result = {
                "error": str(e),
                "agent": self.name,
                "timestamp": datetime.now().isoformat()
            }
            self.save_analysis(error_result)
            return error_result
            
        finally:
            self.is_running = False
            
    def format_analysis_for_display(self, analysis: Dict[str, Any]) -> str:
        """格式化分析结果用于显示"""
        if not analysis:
            return f"{self.name}: 暂无分析结果"
            
        signal = analysis.get("signal", {})
        signal_type = signal.get("signal", "HOLD")
        confidence = signal.get("confidence", 0)
        reason = signal.get("reason", "")
        
        # 信号图标
        signal_icon = {
            "BUY": "🟢",
            "SELL": "🔴", 
            "HOLD": "🟡"
        }.get(signal_type, "❓")
        
        return f"{signal_icon} {self.name}: {signal_type} (置信度: {confidence:.1%}) - {reason}"

class AgentManager:
    """Agent管理器"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.analysis_results: Dict[str, Any] = {}
        
    def register_agent(self, agent: BaseAgent):
        """注册Agent"""
        self.agents[agent.name] = agent
        
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取Agent"""
        return self.agents.get(name)
        
    async def run_all_agents(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """并发运行所有Agent"""
        tasks = []
        for agent in self.agents.values():
            tasks.append(agent.run_analysis(market_data))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        agent_results = {}
        for i, (name, agent) in enumerate(self.agents.items()):
            result = results[i]
            if isinstance(result, Exception):
                agent_results[name] = {
                    "error": str(result),
                    "agent": name,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                agent_results[name] = result
                
        self.analysis_results = agent_results
        return agent_results
        
    def get_all_signals(self) -> List[Dict[str, Any]]:
        """获取所有Agent的信号"""
        signals = []
        for agent_name, result in self.analysis_results.items():
            if "signal" in result:
                signals.append({
                    "agent": agent_name,
                    **result["signal"]
                })
        return signals
        
    def get_agent_status(self) -> Dict[str, Any]:
        """获取所有Agent状态"""
        status = {}
        for name, agent in self.agents.items():
            status[name] = agent.get_status()
        return status

# 全局Agent管理器
agent_manager = AgentManager()