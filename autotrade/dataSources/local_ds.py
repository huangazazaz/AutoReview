"""本地 Parquet 数据源 + 自动缓存写入包装器。

LocalDataSource：从 data/daily/{symbol}.parquet 读取日线数据（支持日期过滤）。
CacheWriter：包装任意 DataSource，get_bars 成功后自动将结果落盘到本地 Parquet。

架构：
  CacheWriter(LocalDataSource) → 读缓存（优先级最高，无网络）
  CacheWriter(TushareDataSource) → 从网络拉取 + 落盘
  CacheWriter(AkShareDataSource) → 从网络拉取 + 落盘

这样首次回测某只股票时通过网络拉取并落盘，
后续回测同一只股票时直接从本地 parquet 读取，零网络开销。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from autotrade.core.interfaces import DataSource
from autotrade.core.models import Bar

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "data/daily"


class LocalDataSource(DataSource):
    """从本地 Parquet 文件读取日线数据的只读数据源。

    文件路径: {data_dir}/{symbol}.parquet
    列: symbol, date, open, high, low, close, volume, amount
    """

    name = "local"

    def __init__(self, data_dir: str = DEFAULT_CACHE_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        path = self._path_for(symbol)
        if not path.exists():
            logger.debug("本地缓存未命中: %s", path)
            return []

        try:
            df = pd.read_parquet(path)
        except Exception as e:
            logger.warning("读取缓存文件失败 %s: %s", path, e)
            return []

        if df.empty:
            return []

        # 确保 date 列为 date 类型并过滤日期范围
        if "date" not in df.columns:
            logger.warning("缓存文件缺少 date 列: %s", path)
            return []

        # pandas 从 parquet 读出的 date 可能是 datetime64[ns] 或 object
        mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
        df_filtered = df.loc[mask]

        if df_filtered.empty:
            logger.debug(
                "缓存数据不覆盖请求的日期范围 %s~%s (缓存: %s~%s)",
                start, end,
                df["date"].min(), df["date"].max(),
            )
            return []

        bars = []
        for _, row in df_filtered.iterrows():
            row_date = row["date"]
            if isinstance(row_date, pd.Timestamp):
                row_date = row_date.date()
            try:
                bar = Bar(
                    symbol=str(row["symbol"]),
                    date=row_date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    amount=float(row["amount"]),
                )
                bars.append(bar)
            except Exception:
                continue

        logger.info("本地加载 %s: %d 根 (请求 %s~%s)", symbol, len(bars), start, end)
        return bars

    def list_symbols(self) -> list[str]:
        """扫描缓存目录，返回已有缓存的股票代码。"""
        symbols = []
        for path in self.data_dir.glob("*.parquet"):
            symbols.append(path.stem)
        return sorted(symbols)

    def _path_for(self, symbol: str) -> Path:
        return self.data_dir / f"{symbol}.parquet"

    # ---- 写入接口（供 CacheWriter 调用）----

    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        """将 bars 写入 Parquet（覆盖模式）。"""
        if not bars:
            return
        records = []
        for b in bars:
            records.append({
                "symbol": b.symbol,
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "amount": b.amount,
            })
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        path = self._path_for(symbol)
        df.to_parquet(path, index=False)
        logger.info("已缓存 %s → %s (%d 根)", symbol, path, len(bars))


class CacheWriter(DataSource):
    """数据源包装器：get_bars 成功时自动把结果落盘到本地 Parquet。

    不修改被包装源的行为（包括失败/返回空），仅附加"写入缓存"副作用。
    注意: name 以 "_" 开头，避免被自动发现注册为普通数据源。
    """

    name = "_cache_writer"

    def __init__(self, inner: DataSource, cache: LocalDataSource | None = None):
        self._inner = inner
        self._cache = cache or LocalDataSource()

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        bars = self._inner.get_bars(symbol, start, end)
        if bars:
            try:
                self._cache.save_bars(symbol, bars)
            except Exception as e:
                logger.warning("缓存写入失败 %s: %s", symbol, e)
        return bars

    def list_symbols(self) -> list[str]:
        return self._inner.list_symbols()
