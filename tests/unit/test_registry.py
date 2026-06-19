"""插件注册表单元测试。"""
import pytest
from autotrade.registry import (
    init_registry, list_datasources, list_indicators,
    list_strategies, list_reporters, get_datasource,
    get_indicator, get_strategy, get_reporter,
)


class TestRegistry:
    def test_init_and_list(self):
        """初始化后至少能列出各类型插件（即使为空目录也应有空列表）。"""
        init_registry(force=True)
        assert isinstance(list_datasources(), list)
        assert isinstance(list_indicators(), list)
        assert isinstance(list_strategies(), list)
        assert isinstance(list_reporters(), list)

    def test_get_nonexistent_raises(self):
        """获取不存在的插件应抛 KeyError。"""
        init_registry(force=True)
        with pytest.raises(KeyError):
            get_datasource("nonexistent")
        with pytest.raises(KeyError):
            get_indicator("nonexistent")
        with pytest.raises(KeyError):
            get_strategy("nonexistent")
        with pytest.raises(KeyError):
            get_reporter("nonexistent")
