"""Screener 注册表测试。"""


def test_screener_registry_dict_exists():
    """注册表应提供 _screens 存储与自动发现接口。"""
    from autotrade.registry import _screens, init_registry
    init_registry(force=True)
    assert isinstance(_screens, dict)


def test_screener_api_functions_exist():
    """register/get/list 三个 screener 接口函数应存在且可调用。"""
    from autotrade.registry import (
        get_screener, list_screens, register_screener,
    )
    assert callable(register_screener)
    assert callable(get_screener)
    assert callable(list_screens)
    # list_screens 在无插件时应返回 list（可能为空）
    assert isinstance(list_screens(), list)


def test_get_screener_raises_on_unknown():
    """查询未注册的 screener 应抛 KeyError。"""
    import pytest
    from autotrade.registry import get_screener
    with pytest.raises(KeyError):
        get_screener("__definitely_not_registered__")
