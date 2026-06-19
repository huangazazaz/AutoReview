"""定时任务触发（APScheduler）。

将 YAML 配置中的定时任务翻译为对 engine 的调用。
支持手动触发: autotrade run-scheduled <job_name>
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from autotrade.core.config import load_config
from autotrade.core.engine import run_backtest
from autotrade.registry import init_registry

logger = logging.getLogger(__name__)


def _get_default_config_path() -> str:
    """获取默认 scheduler.yaml 路径。"""
    import autotrade
    pkg_dir = Path(autotrade.__file__).resolve().parent
    return str(pkg_dir.parent / "config" / "scheduler.yaml")


def load_scheduler_config(path: Optional[str] = None) -> dict[str, Any]:
    """加载定时任务配置。"""
    config_path = Path(path or _get_default_config_path())
    if not config_path.exists():
        return {"jobs": []}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"jobs": []}


def setup_scheduler(config: Optional[dict] = None,
                    background: bool = False):
    """设置并启动 APScheduler。

    Args:
        config: 任务配置字典，None 则从文件加载。
        background: True 用 BackgroundScheduler，False 用 BlockingScheduler。

    Returns:
        APScheduler 实例。
    """
    if config is None:
        config = load_scheduler_config()

    if background:
        scheduler = BackgroundScheduler()
    else:
        scheduler = BlockingScheduler()

    jobs_config = config.get("jobs", [])
    if not jobs_config:
        logger.warning("No scheduled jobs configured.")
        return scheduler

    for job_cfg in jobs_config:
        job_name = job_cfg.get("name", "unnamed")
        cron_expr = job_cfg.get("cron", "")
        command = job_cfg.get("command", {})
        reporters = job_cfg.get("reporters", ["console"])

        if not cron_expr or not command:
            logger.warning("Skipping job '%s': incomplete config", job_name)
            continue

        try:
            # 解析 cron 表达式: "30 15 * * 1-5"
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                logger.warning("Invalid cron expression for job '%s': %s",
                               job_name, cron_expr)
                continue

            minute, hour, day, month, day_of_week = parts

            scheduler.add_job(
                func=_execute_job,
                trigger="cron",
                args=[command, reporters],
                id=job_name,
                name=job_name,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                replace_existing=True,
            )
            logger.info("Scheduled job '%s': %s", job_name, cron_expr)

        except Exception as e:
            logger.error("Failed to schedule job '%s': %s", job_name, e)

    return scheduler


def run_now(job_name: str) -> None:
    """立即执行一个定时任务（用于手动触发）。"""
    config = load_scheduler_config()
    for job_cfg in config.get("jobs", []):
        if job_cfg.get("name") == job_name:
            command = job_cfg.get("command", {})
            reporters = job_cfg.get("reporters", ["console"])
            _execute_job(command, reporters)
            return
    logger.error("Job '%s' not found in scheduler config", job_name)


def _execute_job(command: dict, reporters: list[str]) -> None:
    """执行一个任务（将配置翻译为 engine 调用）。"""
    init_registry()

    cmd_type = command.get("type", "backtest")
    strategy = command.get("strategy", "ma_cross")
    universe = command.get("universe", "all")
    symbols = command.get("symbols", "all")
    top = command.get("top", 20)
    datasource = command.get("datasource", "akshare")

    end = date.today()

    logger.info("Scheduled %s: strategy=%s", cmd_type, strategy)
    run_backtest(
        strategy_name=strategy,
        symbols=universe if cmd_type == "scan" else symbols,
        end=end,
        datasource_name=datasource,
        reporter_names=tuple(reporters),
    )


def main():
    """调度器主入口（供 console_scripts 使用）。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    scheduler = setup_scheduler(background=False)
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
