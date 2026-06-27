"""指标插件 —— 自动发现并注册目录内所有指标。"""
from autotrade.registry import register_indicator, get_indicator, list_indicators

from autotrade.indicators.atr import ATR
