"""批量下载 A 股近 3 年日线数据并缓存到本地 Parquet。

用法:
    python scripts/download_stocks.py                     # 默认用 akshare 下载全部（排除 920 开头）
    python scripts/download_stocks.py --source tushare    # 用 Tushare 下载（需在 config/settings.yaml 配 token）
    python scripts/download_stocks.py --dry-run           # 仅列出，不下载
    python scripts/download_stocks.py --symbols 000001,600519  # 只下载指定股票
    python scripts/download_stocks.py --csv data/a_stock_list.csv  # 从 CSV 文件读取股票列表
    python scripts/download_stocks.py --force             # 强制重新下载，忽略已有缓存

特性:
    - 数据源: akshare (免费, 默认) 或 tushare (需 token)
    - 自动排除 920 开头的股票（北交所特定板块）
    - 每分钟最多 50 次请求，带随机冗余等待避免限流
    - 支持断点续传（已缓存且日期范围覆盖的跳过）
    - 失败自动重试（最多 3 次），指数退避
    - 保存格式与 LocalDataSource 完全兼容
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "daily"
LOG_FILE = PROJECT_ROOT / "data" / "logs" / "download_stocks.log"

# 默认下载最近 3 年
LOOKBACK_YEARS = 3
END_DATE = date.today()
START_DATE = END_DATE.replace(year=END_DATE.year - LOOKBACK_YEARS)

# 限流: 每分钟 50 次 → 最小间隔 1.2s + 随机冗余 0.3~1.8s
RATE_LIMIT_PER_MINUTE = 60
MIN_INTERVAL_SEC = 60.0 / RATE_LIMIT_PER_MINUTE   # 1.2s
JITTER_LOW_SEC = 0
JITTER_HIGH_SEC = 0

# 重试
MAX_RETRIES = 1
RETRY_BACKOFF_BASE = 5  # 秒

# 排除前缀
EXCLUDED_PREFIXES = ("920",)

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

os.makedirs(PROJECT_ROOT / "data" / "logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("download_stocks")


# ===================================================================
# 数据源适配层
# ===================================================================

class _DataSourceAdapter:
    """统一的数据源接口，封装不同后端的差异。"""

    def list_symbols(self) -> list[str]:
        raise NotImplementedError

    def get_bars_df(self, symbol: str, start: date, end: date) -> pd.DataFrame | None:
        """返回原始 DataFrame 或 None。"""
        raise NotImplementedError

    @staticmethod
    def to_cache_records(symbol: str, df: pd.DataFrame) -> list[dict]:
        """将原始 DataFrame 转为统一缓存记录格式。"""
        raise NotImplementedError


class _AkShareAdapter(_DataSourceAdapter):
    """AkShare (东方财富) 数据源。"""

    def list_symbols(self) -> list[str]:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return []
        return df["代码"].tolist()

    def get_bars_df(self, symbol: str, start: date, end: date) -> pd.DataFrame | None:
        import akshare as ak
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",
            )
        except Exception:
            return None
        if df is None or df.empty:
            return None
        return df

    @staticmethod
    def to_cache_records(symbol: str, df: pd.DataFrame) -> list[dict]:
        records = []
        for _, row in df.iterrows():
            try:
                row_date = row["日期"]
                if isinstance(row_date, datetime):
                    row_date = row_date.date()
                elif isinstance(row_date, pd.Timestamp):
                    row_date = row_date.date()
                records.append({
                    "symbol": symbol,
                    "date": row_date,
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": float(row["成交量"]),
                    "amount": float(row["成交额"]),
                })
            except Exception:
                continue
        return records


class _TushareAdapter(_DataSourceAdapter):
    """Tushare Pro 数据源。

    从 config/settings.yaml 读取 token。
    """

    def __init__(self, token: str):
        import tushare as ts
        self._pro = ts.pro_api(token)

    def list_symbols(self) -> list[str]:
        try:
            df = self._pro.stock_basic(
                exchange="", list_status="L",
                fields="ts_code,symbol",
            )
            if df is None or df.empty:
                return []
            return df["symbol"].tolist()
        except Exception:
            return []

    def get_bars_df(self, symbol: str, start: date, end: date) -> pd.DataFrame | None:
        ts_code = _symbol_to_ts_code(symbol)
        try:
            df = self._pro.daily(
                ts_code=ts_code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        except Exception:
            return None
        if df is None or df.empty:
            return None
        return df

    @staticmethod
    def to_cache_records(symbol: str, df: pd.DataFrame) -> list[dict]:
        records = []
        for _, row in df.iterrows():
            try:
                trade_date = row["trade_date"]
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, "%Y%m%d").date()
                records.append({
                    "symbol": symbol,
                    "date": trade_date,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["vol"]),
                    # Tushare amount 单位是千元，转为元（与 AkShare 统一）
                    "amount": float(row["amount"]) * 1000,
                })
            except Exception:
                continue
        return records


def _symbol_to_ts_code(symbol: str) -> str:
    """将 6 位代码转为 Tushare ts_code 格式。

    规则:
        000xxx, 001xxx, 002xxx, 003xxx → .SZ
        300xxx, 301xxx → .SZ
        600xxx, 601xxx, 603xxx, 605xxx → .SH
        430xxx, 830xxx, 831xxx, 832xxx, 833xxx, 834xxx, 835xxx, 836xxx,
        837xxx, 838xxx, 839xxx, 870xxx, 871xxx, 872xxx, 873xxx → .BJ
        688xxx → .SH (科创板)
        920xxx → .BJ (北交所)
    """
    code = symbol.zfill(6)
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{code}.SZ"
    elif code.startswith(("600", "601", "603", "605", "688")):
        return f"{code}.SH"
    # 北交所
    if code.startswith(("43", "83", "87", "92")):
        return f"{code}.BJ"
    # fallback: 根据首位猜测
    if code[0] in ("0", "2", "3"):
        return f"{code}.SZ"
    if code[0] in ("6",):
        return f"{code}.SH"
    return f"{code}.SZ"


# ===================================================================
# Tushare token 读取
# ===================================================================

def _load_tushare_token() -> str:
    """从 config/settings.yaml 或环境变量读取 Tushare token。"""
    # 优先环境变量
    env_token = os.environ.get("AUTOTRADE__DATASOURCE__SOURCES__TUSHARE__TOKEN", "")
    if env_token:
        return env_token

    # 从 YAML 配置读取
    config_path = PROJECT_ROOT / "config" / "settings.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            ds = cfg.get("datasource", {})
            sources = ds.get("sources", {}) or {}
            tushare_cfg = sources.get("tushare", {}) or {}
            token = tushare_cfg.get("token", "")
            if token:
                return str(token)
        except Exception:
            pass

    return ""


def _read_symbols_from_csv(csv_path: str) -> list[str]:
    """从 CSV 文件读取股票代码列表。

    支持以下列名（大小写不敏感）: code, symbol, 代码
    """
    path = Path(csv_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        logger.error("CSV 文件不存在: %s", path)
        return []

    df = pd.read_csv(path, dtype=str)
    if df.empty:
        return []

    # 自动识别代码列
    code_col = None
    for col in df.columns:
        if col.lower() in ("code", "symbol", "代码"):
            code_col = col
            break
    if code_col is None:
        code_col = df.columns[0]
        logger.warning("未找到 code/symbol/代码 列，使用首列: %s", code_col)

    symbols = df[code_col].dropna().str.strip().str.zfill(6).tolist()
    symbols = list(dict.fromkeys(symbols))  # 去重保序
    return symbols


# ===================================================================
# 缓存检查
# ===================================================================

def is_already_cached(symbol: str) -> bool:
    """检查股票是否已缓存且覆盖目标日期范围（容忍 7 天偏差）。"""
    path = CACHE_DIR / f"{symbol}.parquet"
    if not path.exists():
        return False

    try:
        df = pd.read_parquet(path)
        if df.empty or "date" not in df.columns:
            return False

        cached_max = pd.Timestamp(df["date"].max())
        recent_enough = cached_max >= pd.Timestamp(END_DATE) - pd.Timedelta(days=7)
        if not recent_enough:
            return False

        cached_min = pd.Timestamp(df["date"].min())
        covers_start = cached_min <= pd.Timestamp(START_DATE) + pd.Timedelta(days=7)
        return covers_start
    except Exception:
        return False


# ===================================================================
# 单股下载
# ===================================================================

def download_one_stock(adapter: _DataSourceAdapter, symbol: str) -> bool:
    """下载单只股票数据并保存为 parquet。

    Returns:
        True 成功，False 失败。
    """
    df = adapter.get_bars_df(symbol, START_DATE, END_DATE)
    if df is None or df.empty:
        logger.warning("[%s] 返回数据为空，跳过", symbol)
        return False

    records = adapter.to_cache_records(symbol, df)
    if not records:
        logger.warning("[%s] 解析后无有效数据行", symbol)
        return False

    # 保存为 parquet（与 LocalDataSource.save_bars 格式兼容）
    df_out = pd.DataFrame(records)
    df_out["date"] = pd.to_datetime(df_out["date"])
    df_out.sort_values("date", inplace=True)
    df_out.reset_index(drop=True, inplace=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{symbol}.parquet"
    df_out.to_parquet(path, index=False)

    dates = sorted(r["date"] for r in records)
    date_range = f"{dates[0]} ~ {dates[-1]}"
    logger.info("[%s] ✓ 已缓存 %d 根 K 线 (%s)", symbol, len(records), date_range)
    return True


def download_with_retry(adapter: _DataSourceAdapter, symbol: str) -> bool:
    """带重试的单股下载。"""
    for attempt in range(1, MAX_RETRIES + 1):
        if download_one_stock(adapter, symbol):
            return True
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 2)
            logger.warning("[%s] 第 %d 次失败，%.1f 秒后重试...", symbol, attempt, wait)
            time.sleep(wait)
    logger.error("[%s] ✗ 重试 %d 次后仍失败，放弃", symbol, MAX_RETRIES)
    return False


def random_wait():
    """随机等待，确保不超过限流阈值。"""
    wait = MIN_INTERVAL_SEC
    #  + random.uniform(JITTER_LOW_SEC, JITTER_HIGH_SEC)
    time.sleep(wait)


# ===================================================================
# 主流程
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="批量下载 A 股近 3 年日线数据并缓存"
    )
    parser.add_argument(
        "--source", type=str, default="auto",
        choices=["auto", "akshare", "tushare"],
        help="数据源: auto=自动选择可用源, akshare=东方财富, tushare=Tushare Pro (默认: auto)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅列出待下载股票，不实际下载"
    )
    parser.add_argument(
        "--symbols", type=str, default="",
        help="逗号分隔的股票代码列表（默认: 全部）"
    )
    parser.add_argument(
        "--csv", type=str, default="",
        help="从 CSV 文件读取股票列表（需有 code 列，如 scripts/export_stock_list.py 导出结果）"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制重新下载，忽略已有缓存"
    )
    parser.add_argument(
        "--start", type=str, default="",
        help="起始日期 YYYYMMDD（默认: 3 年前）"
    )
    parser.add_argument(
        "--end", type=str, default="",
        help="截止日期 YYYYMMDD（默认: 今天）"
    )
    args = parser.parse_args()

    global START_DATE, END_DATE
    if args.start:
        START_DATE = datetime.strptime(args.start, "%Y%m%d").date()
    if args.end:
        END_DATE = datetime.strptime(args.end, "%Y%m%d").date()

    # ---- 初始化数据源适配器 ----
    tushare_token = _load_tushare_token()

    if args.source == "tushare":
        if not tushare_token:
            logger.error(
                "Tushare token 未配置。请在 config/settings.yaml 中设置 "
                "datasource.sources.tushare.token 或设置环境变量 "
                "AUTOTRADE__DATASOURCE__SOURCES__TUSHARE__TOKEN"
            )
            return 1
        adapter = _TushareAdapter(tushare_token)
    elif args.source == "akshare":
        adapter = _AkShareAdapter()
    else:  # auto: 先测 akshare，不可用则切 tushare
        logger.info("自动检测可用数据源...")
        adapter = _AkShareAdapter()
        try:
            # 快速探测：尝试获取一只股票的数据来验证连通性
            test_df = adapter.get_bars_df("000001", END_DATE - timedelta(days=7), END_DATE)
            if test_df is not None and not test_df.empty:
                logger.info("✓ AkShare (东方财富) 可用，使用 akshare")
            else:
                raise ConnectionError("AkShare 返回空数据")
        except Exception as e:
            logger.warning("AkShare 不可用 (%s)，尝试切换 Tushare...", str(e)[:80])
            if tushare_token:
                adapter = _TushareAdapter(tushare_token)
                logger.info("✓ 已切换到 Tushare")
            else:
                logger.error(
                    "所有数据源均不可用。AkShare 连接失败，且 Tushare token 未配置。\n"
                    "请在 config/settings.yaml 中配置 Tushare token，"
                    "或检查网络连接后重试。"
                )
                return 1

    logger.info("=" * 60)
    logger.info("AutoTrade 股票数据批量下载")
    logger.info("数据源: %s", args.source)
    logger.info("日期范围: %s ~ %s", START_DATE, END_DATE)
    logger.info("缓存目录: %s", CACHE_DIR)
    logger.info("限流: %d 次/分钟 (间隔 %.1fs + 随机 %.1f~%.1fs)",
                RATE_LIMIT_PER_MINUTE, MIN_INTERVAL_SEC, JITTER_LOW_SEC, JITTER_HIGH_SEC)
    logger.info("=" * 60)

    # ---- 获取股票列表 ----
    if args.csv:
        symbols = _read_symbols_from_csv(args.csv)
        if not symbols:
            logger.error("从 CSV 文件未读取到有效股票代码")
            return 1
        symbols = [s for s in symbols if not s.startswith(EXCLUDED_PREFIXES)]
        logger.info("从 CSV 读取: %d 只股票 (%s)", len(symbols), args.csv)
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        symbols = [s for s in symbols if not s.startswith(EXCLUDED_PREFIXES)]
        logger.info("指定股票: %d 只", len(symbols))
    else:
        logger.info("正在获取全市场 A 股列表...")
        try:
            all_codes = adapter.list_symbols()
        except Exception as e:
            all_codes = []
            logger.error("获取股票列表时网络异常: %s", e)
        if not all_codes:
            logger.error("获取股票列表失败：返回为空")
            if args.source == "akshare":
                token = _load_tushare_token()
                if token:
                    logger.info(
                        "💡 提示: AkShare (东方财富) 接口可能不可用，"
                        "试试改用 Tushare:\n"
                        "   python scripts/download_stocks.py --source tushare"
                    )
                else:
                    logger.info(
                        "💡 提示: 请检查网络连接，或在 config/settings.yaml 中配置 "
                        "Tushare token 后使用 --source tushare"
                    )
            return 1
        logger.info("全市场共 %d 只股票", len(all_codes))

        excluded = [c for c in all_codes if c.startswith(EXCLUDED_PREFIXES)]
        symbols = [c for c in all_codes if not c.startswith(EXCLUDED_PREFIXES)]
        if excluded:
            logger.info("排除 %d 只 920 开头的股票: %s...",
                        len(excluded), excluded[:10])

    logger.info("待处理: %d 只股票", len(symbols))

    if not symbols:
        logger.error("没有需要处理的股票")
        return 1

    # ---- 过滤已缓存的（除非 --force）----
    if not args.force:
        to_download = [s for s in symbols if not is_already_cached(s)]
        skipped = len(symbols) - len(to_download)
        if skipped:
            logger.info("跳过 %d 只已缓存且覆盖日期范围的股票", skipped)
    else:
        to_download = symbols
        logger.info("强制模式: 将重新下载全部 %d 只股票", len(to_download))

    if not to_download:
        logger.info("所有股票均已缓存，无需下载 ✨")
        return 0

    if args.dry_run:
        logger.info("DRY-RUN 模式: 以下 %d 只待下载:", len(to_download))
        for s in to_download:
            print(f"  {s}")
        return 0

    # ---- 批量下载 ----
    total = len(to_download)
    success = 0
    fail = 0
    t0 = time.time()

    for i, symbol in enumerate(to_download, 1):
        logger.info("[%d/%d] 正在下载 %s ...", i, total, symbol)

        ok = download_with_retry(adapter, symbol)
        if ok:
            success += 1
        else:
            fail += 1

        # 进度统计
        elapsed = time.time() - t0
        avg_per_stock = elapsed / i
        eta_seconds = avg_per_stock * (total - i)
        logger.info(
            "进度: %d/%d | 成功: %d | 失败: %d | 已用时: %s | 预计剩余: %s",
            i, total, success, fail,
            _fmt_duration(elapsed),
            _fmt_duration(eta_seconds),
        )

        # 限流等待（最后一只不用等）
        if i < total:
            random_wait()

    # ---- 汇总 ----
    elapsed = time.time() - t0
    logger.info("=" * 60)
    logger.info("下载完成! 总耗时: %s", _fmt_duration(elapsed))
    logger.info("成功: %d | 失败: %d | 总计: %d", success, fail, total)
    logger.info("缓存文件数: %d", len(list(CACHE_DIR.glob("*.parquet"))))
    logger.info("=" * 60)

    return 0 if fail == 0 else 1


def _fmt_duration(seconds: float) -> str:
    """格式化时长。"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m{s}s"
    h, m = divmod(m, 60)
    return f"{h}h{m}m{s}s"


if __name__ == "__main__":
    sys.exit(main())
