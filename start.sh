#!/usr/bin/env bash
# ============================================================
#  AutoTrade 后端启动脚本 (macOS / Linux)
#  启动 API 服务器 → http://localhost:8080
# ============================================================

set -e

# ---------- 颜色 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------- 切换到脚本所在目录 ----------
cd "$(dirname "$0")"

# ---------- Banner ----------
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║${RESET}  ${BOLD}AutoTrade  A股量化回测系统${RESET}              ${CYAN}║${RESET}"
echo -e "${CYAN}║${RESET}  Web: ${GREEN}http://localhost:8080${RESET}                  ${CYAN}║${RESET}"
echo -e "${CYAN}║${RESET}  Docs: ${GREEN}http://localhost:8080/docs${RESET}             ${CYAN}║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ---------- 检查 Python ----------
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" --version 2>&1 | awk '{print $2}')
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}[ERROR]${RESET} 未找到 Python 3.10+，请先安装"
    echo "  macOS: brew install python@3.12"
    echo "  Ubuntu: sudo apt install python3.12"
    exit 1
fi
echo -e "${GREEN}[OK]${RESET} $PYTHON $PY_VER"

# ---------- 激活虚拟环境（如果存在）----------
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}[OK]${RESET} 已激活虚拟环境 .venv"
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}[OK]${RESET} 已激活虚拟环境 venv"
fi

# ---------- 检查关键依赖 ----------
if ! $PYTHON -c "import fastapi" &>/dev/null; then
    echo -e "${YELLOW}[WARN]${RESET} 缺少依赖，正在安装..."
    echo ""
    if [ -f "pyproject.toml" ]; then
        pip install -e ".[api]" -q
    else
        pip install fastapi uvicorn -q
    fi
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR]${RESET} 依赖安装失败，请手动执行:"
        echo "  pip install -e \".[api]\""
        exit 1
    fi
    echo -e "${GREEN}[OK]${RESET} 依赖安装完成"
else
    echo -e "${GREEN}[OK]${RESET} 依赖已就绪"
fi

# ---------- 确保数据目录存在 ----------
mkdir -p data/cache data/results data/logs

# ---------- 启动服务器 ----------
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}正在启动 API 服务器...${RESET}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "  按 ${YELLOW}Ctrl+C${RESET} 停止服务器"
echo ""

$PYTHON -m autotrade.api
