# AutoTrade 前端启动文档

## 简介

AutoTrade 前端是一个纯静态 SPA（单页应用），由 FastAPI 后端统一托管。
无需单独启动前端服务器，启动后端即可访问。

## 快速启动

### 方式一：启动脚本（推荐）

```bash
# Windows 双击
start.bat
```

### 方式二：命令行

```bash
# 项目根目录
python -m autotrade.api
```

### 方式三：直接 uvicorn

```bash
uvicorn autotrade.api.server:app --host 0.0.0.0 --port 8080 --reload
```

## 访问地址

| 页面 | URL |
|------|-----|
| 仪表盘 | http://localhost:8080 |
| 单股分析 | http://localhost:8080/#/analyze |
| 批量回测 | http://localhost:8080/#/backtest |
| K线数据 | http://localhost:8080/#/bars |
| 分组管理 | http://localhost:8080/#/groups |
| API 文档 | http://localhost:8080/docs |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + Uvicorn |
| 前端 | 原生 JS (SPA + Hash 路由) |
| 图表 | ECharts 5.5 |
| 字体 | Inter (Google Fonts) |
| 图标 | 内联 SVG (Lucide 风格) |

## 文件结构

```
frontend/
├── index.html          # 入口页面
├── css/
│   └── style.css       # 全局样式 (Swiss Minimal 设计系统)
└── js/
    ├── icons.js        # SVG 图标库 (28 个图标)
    ├── api.js          # API 客户端 (封装所有后端接口)
    ├── router.js       # Hash 路由 (SPA)
    ├── app.js          # 全局工具函数 & 初始化
    └── views/
        ├── dashboard.js  # 仪表盘
        ├── analyze.js    # 单股分析 (净值曲线 + 交易记录)
        ├── backtest.js   # 批量回测 (收益率排行 + 对比图)
        ├── bars.js       # K线数据 (蜡烛图 + 数据表)
        └── groups.js     # 分组管理 (CRUD)
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/analyze` | 单股回测分析 |
| POST | `/backtest` | 批量/分组回测 |
| POST | `/bars` | 日线 OHLCV 查询 |
| GET | `/strategies` | 策略列表 |
| GET | `/datasources` | 数据源列表 |
| GET | `/cache/stocks` | 本地缓存股票列表 |
| GET | `/groups` | 分组列表 |
| POST | `/groups` | 创建分组 |
| GET | `/groups/{id}` | 获取分组 |
| PUT | `/groups/{id}` | 更新分组 |
| DELETE | `/groups/{id}` | 删除分组 |
| GET | `/health` | 健康检查 |

## 开发调试

1. 启动后端（自动开启 `--reload`，代码变更自动重启）
2. 前端修改后**刷新浏览器**即可（纯静态文件，无需构建）
3. API 调试：访问 http://localhost:8080/docs 使用 Swagger UI
