"""配置加载单元测试。"""
import os
import pytest
import tempfile
from autotrade.core.config import load_config, get_config


class TestConfig:
    def test_load_defaults(self):
        """加载默认配置应返回合理的默认值。"""
        config = load_config(force_reload=True)
        assert config["backtest"]["initial_capital"] >= 100000
        assert config["backtest"]["commission_rate"] == 0.0003
        assert config["datasource"]["default"] == "failover"
        assert config["datasource"]["failover"] is True
        assert "tushare" in config["datasource"]["sources"]
        assert "akshare" in config["datasource"]["sources"]
        assert config["cache"]["enabled"] is True

    def test_env_override(self):
        """环境变量应覆盖配置。"""
        os.environ["AUTOTRADE__BACKTEST__INITIAL_CAPITAL"] = "99999"
        os.environ["AUTOTRADE__DATASOURCE__DEFAULT"] = "tushare"
        config = load_config(force_reload=True)
        assert config["backtest"]["initial_capital"] == 99999
        assert config["datasource"]["default"] == "tushare"
        # 清理环境变量
        del os.environ["AUTOTRADE__BACKTEST__INITIAL_CAPITAL"]
        del os.environ["AUTOTRADE__DATASOURCE__DEFAULT"]
