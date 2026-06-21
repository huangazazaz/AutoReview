"""导出全量 A 股股票列表（代码、名称、板块）到 CSV。

用法:
    python scripts/export_stock_list.py                     # 默认 akshare
    python scripts/export_stock_list.py --source baostock   # 用 baostock
    python scripts/export_stock_list.py --output ./my_stocks.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 板块判断逻辑
# ---------------------------------------------------------------------------

def get_board(code: str) -> str:
    """根据 6 位股票代码推导所属板块。"""
    code = code.zfill(6)

    if code.startswith("688"):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("000", "001", "002", "003")):
        return "深市主板"
    if code.startswith(("600", "601", "603", "605")):
        return "沪市主板"
    # 北交所
    if code.startswith(("43", "83", "87", "92")):
        return "北交所"
    # 兜底
    if code[0] in ("0", "2", "3"):
        return "深市主板"
    if code[0] == "6":
        return "沪市主板"
    return "其他"


def export_via_akshare(output_path: str):
    """通过 AKShare (东方财富) 获取。"""
    import akshare as ak

    print("正在连接东方财富...")
    df = ak.stock_zh_a_spot_em()
    if df is None or df.empty:
        print("❌ AKShare 返回空数据，请检查网络")
        return 1

    result = pd.DataFrame({
        "code": df["代码"].str.zfill(6),
        "name": df["名称"],
        "board": df["代码"].apply(get_board),
    })
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    _print_summary(result, output_path)
    return 0


def export_via_baostock(output_path: str):
    """通过 Baostock 获取。"""
    import baostock as bs

    print("正在连接 Baostock...")
    lg = bs.login()
    if lg.error_code != "0":
        print(f"❌ Baostock 登录失败: {lg.error_msg}")
        return 1

    rs = bs.query_stock_basic()

    rows = []
    while rs.next():
        rows.append(rs.get_row_data())

    bs.logout()

    if not rows:
        print("❌ Baostock 返回空数据")
        return 1

    # rs.fields: ['code', 'code_name', 'ipoDate', 'outDate', 'type', 'status']
    data = pd.DataFrame(rows, columns=rs.fields)

    # 过滤：只保留 A 股（type == '1'），排除指数（type == '2'）等
    if "type" in data.columns:
        data = data[data["type"] == "1"]
        print(f"过滤后 A 股: {len(data)} 只")
    else:
        # 兜底：排除名称含"指数"的行
        data = data[~data["code_name"].str.contains("指数", na=False)]

    # code 格式: sh.600000 / sz.000001 / bj.430xxx
    raw = data["code"].str.split(".", expand=True)
    result = pd.DataFrame({
        "code": raw[1].str.zfill(6),
        "name": data["code_name"],
    })
    result["board"] = result["code"].apply(get_board)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    _print_summary(result, output_path)
    return 0


def _print_summary(df: pd.DataFrame, output_path: str):
    print(f"✅ 已保存 {len(df)} 只股票到 {output_path}")
    print()
    print("前 10 只预览:")
    print(df.head(10).to_string(index=False))
    print()
    print("板块分布:")
    for board, count in df["board"].value_counts().items():
        print(f"  {board}: {count} 只")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="导出 A 股股票列表到 CSV")
    parser.add_argument(
        "--source", choices=["akshare", "baostock"], default="akshare",
        help="数据源 (默认: akshare)",
    )
    parser.add_argument(
        "--output", type=str, default="",
        help="输出路径 (默认: data/a_stock_list.csv)",
    )
    args = parser.parse_args()

    output = args.output or str(PROJECT_ROOT / "data" / "a_stock_list.csv")

    if args.source == "akshare":
        code = export_via_akshare(output)
    else:
        code = export_via_baostock(output)

    sys.exit(code)


if __name__ == "__main__":
    main()
