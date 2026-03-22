"""
周度选股顾问模块 - WeeklyAdvisor
为用户提供下周能实现5%盈利目标的选股建议
"""
from .advisor import WeeklyAdvisor
from .models import WeeklyReport, StockRecommendation, StockCandidate

__all__ = ["WeeklyAdvisor", "WeeklyReport", "StockRecommendation", "StockCandidate"]
