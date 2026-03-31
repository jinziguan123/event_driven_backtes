# 事件驱动回测工具

`event_driven_backtest` 是一个独立的事件驱动回测子项目，面向 A 股股票多头场景，当前采用 `ClickHouse + MySQL` 双存储架构：

- 分钟 K 线从 ClickHouse 读取
- 证券元数据（symbol -> symbol_id）从 MySQL 读取

当前版本已经提供：

- 基于 ClickHouse 的分钟线回测数据读取
- 基于 MySQL 的证券元数据映射
- `1m` 到更大周期的 K 线聚合
- 类式策略、脚本式策略双模式接入
- 通达信常用函数 Python 实现入口
- 事件驱动撮合、持仓管理、绩效统计
- MySQL + Parquet/JSON 的结果持久化
- FastAPI 后端接口
- React + Vite 前端结果展示页面
- 策略目录自动发现与前端下拉选择
- 独立股票池管理与回测复用
- 分钟级双均线 5/20 示例策略
- 策略收益曲线、基准收益曲线、超额收益与最大回撤区间可视化

## 1. 项目结构

```text
event_driven_backtest/
├── backend/
│   ├── api/                # FastAPI 接口
│   ├── core/               # 核心配置、事件、领域模型
│   ├── data/               # ClickHouse/MySQL 数据读取、K 线聚合、DataPortal
│   ├── engine/             # 账户、撮合、事件总线、回测执行、指标计算
│   ├── runner/             # 回测服务编排
│   ├── storage/            # MySQL 与结果文件持久化
│   ├── strategies/         # 内置示例策略
│   ├── strategy_sdk/       # 策略加载与适配层
│   ├── tdx/                # 通达信指标函数运行时
│   └── tests/              # 后端单元测试
├── frontend/
│   ├── src/components/     # 图表、表格、摘要卡片等组件
│   ├── src/pages/          # 创建页、列表页、详情页
│   └── src/api/            # 前端 API 调用封装
└── README.md
```

## 2. 设计目标

这个子项目的重点是把“回测引擎”和“策略实现”拆开，便于后续持续迭代策略，而不用频繁改动底层框架。

- `engine/` 负责事件循环、撮合、持仓与收益计算
- `strategy_sdk/` 负责把用户策略适配为统一接口
- `tdx/` 负责给策略提供通达信风格函数支持
- `storage/` 负责回测结果与产物落盘
- `frontend/` 负责回测任务发起与结果展示

## 3. 运行环境

### 3.1 Python 环境

项目已经按你的本机环境约定，默认使用：

```bash
source /Users/jinziguan/.virtualenvs/Python_Calculation/bin/activate
```

如需补依赖，可执行：

```bash
pip install -r /Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/requirements.txt
```

### 3.2 Node 环境

前端基于 Vite，建议使用 Node 18+。

安装依赖：

```bash
cd /Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/frontend
npm install
```

## 4. 数据来源说明

### 4.1 分钟线数据（ClickHouse）

回测分钟线由以下模块读取：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/data/raw_loader.py`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/data/clickhouse_loader.py`

默认查询表：`quant_data.stock_bar_1m`（可通过环境变量覆盖连接）。

### 4.2 证券元数据（MySQL）

`raw_loader` 在读取分钟线前，会先通过 MySQL 的 `stock_symbol` 表完成 `symbol -> symbol_id` 映射。

相关模块：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/data/db_clients.py`

默认 MySQL 库：`quant_data`，默认表：`stock_symbol`。

### 4.3 股票池元数据

股票池管理默认走 MySQL（表：`stock_pool`、`stock_pool_symbol`，含 `owner_key` 轻量隔离）。

默认不回退；如需在 MySQL 异常时临时回退 SQLite，可显式设置 `EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK=1`。

### 4.4 复权逻辑

当前支持的复权方式：

- `qfq`：当前版本会回退为原始价格并告警（尚未接入独立复权因子）
- `none`：不复权
- `hfq`：接口已预留，首版尚未实现

### 4.5 K 线周期

当前原始数据频率为分钟线，回测时可进一步聚合为更高周期，例如：

- `1m`
- `5m`
- `15m`
- `30m`
- `60m`
- 其他聚合周期（只要聚合器支持）

相关聚合逻辑位于：`/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/data/aggregator.py`

## 5. 回测配置项

回测创建接口当前支持的核心参数如下：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `symbols` | 回测股票列表；与 `pool_id` 二选一 | 可空 |
| `pool_id` | 已保存股票池 ID | 可空 |
| `name` | 回测任务名称 | `未命名回测` |
| `strategy_name` | 策略显示名称 | `未指定策略` |
| `strategy_path` | 策略文件路径 | 默认示例策略 |
| `strategy_type` | 策略类型，`class` / `script` | `class` |
| `initial_cash` | 初始资金 | `1000000` |
| `start_datetime` | 回测开始时间 | 可空 |
| `end_datetime` | 回测结束时间 | 可空 |
| `bar_frequency` | 目标 K 线周期 | `1m` |
| `max_positions` | 最大持仓股票数量 | `5` |
| `slippage` | 滑点 | `0.0` |
| `commission` | 手续费 | `0.0003` |
| `stamp_duty` | 印花税 | `0.001` |
| `adjustment` | 复权方式 | `qfq` |
| `match_mode` | 成交模式，`close` / `next_open` / `limit` | `next_open` |
| `benchmark` | 基准代码 | `000300.SH` |

配置定义位于：`/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/core/config.py`

## 6. 快速启动

### 6.1 一键启动前后端

已新增一键启动脚本：`/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/start_dev.sh`

在 `event_driven_backtest` 目录执行：

```bash
cd /Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest
./start_dev.sh
```

脚本默认会完成以下动作：

- 检查当前 `python`、`npm` 是否可用
- 检查后端依赖 `uvicorn`、`fastapi` 是否已安装
- 如前端依赖未安装，则自动执行 `npm install`
- 在仓库根目录启动后端，自动补齐 `PYTHONPATH`
- 在前台启动前端开发服务器
- 当前端退出时，自动回收后端进程

默认地址：

- 前端：`http://127.0.0.1:5174`
- 后端：`http://127.0.0.1:8000`
- Swagger：`http://127.0.0.1:8000/docs`

### 6.2 可选环境变量

如需显式指定虚拟环境激活脚本，可在执行前设置：

```bash
export BACKTEST_VENV_ACTIVATE=/path/to/venv/bin/activate
./start_dev.sh
```

脚本还支持以下可选变量：

- `BACKEND_HOST`
- `BACKEND_PORT`
- `FRONTEND_HOST`
- `FRONTEND_PORT`
- `EVENT_BT_MYSQL_HOST` / `EVENT_BT_MYSQL_PORT` / `EVENT_BT_MYSQL_USER` / `EVENT_BT_MYSQL_PASSWORD` / `EVENT_BT_MYSQL_DATABASE`
- `EVENT_BT_CLICKHOUSE_HOST` / `EVENT_BT_CLICKHOUSE_PORT` / `EVENT_BT_CLICKHOUSE_USER` / `EVENT_BT_CLICKHOUSE_PASSWORD` / `EVENT_BT_CLICKHOUSE_DATABASE`
- `EVENT_BT_STOCK_POOL_BACKEND`（`mysql` 或 `sqlite`）
- `EVENT_BT_OWNER_KEY`（股票池 owner_key，默认 `default`）
- `EVENT_BT_STOCK_POOL_ALLOW_SQLITE_FALLBACK`（默认 `0`，MySQL 不可用时报错）
- `EVENT_BT_RESULT_DB_BACKEND`（`mysql` 或 `sqlite`，默认 `mysql`）
- `EVENT_BT_RESULT_DB_ALLOW_SQLITE_FALLBACK`（默认 `0`，MySQL 不可用时报错）

若未设置 `EVENT_BT_*`，会自动回退到同名通用变量（如 `MYSQL_HOST`、`CLICKHOUSE_HOST`），再回退到内置默认值。

### 6.3 前后端联调说明

前端通过相对路径 `/api` 访问后端接口。

当前已经在 `vite.config.ts` 中内置开发代理：

- `/api -> http://127.0.0.1:8000`

因此在本地开发环境中，可以直接从前端页面发起：

- `http://127.0.0.1:5174/api/backtests`
- `http://127.0.0.1:5174/api/strategies`

这类请求会自动代理到后端，不再返回 Vite 本身的 404。

## 7. API 说明

### 7.1 创建回测

接口：

```text
POST /api/backtests
```

请求示例：

```json
{
  "name": "演示回测",
  "strategy_name": "demo_buy_hold",
  "strategy_type": "class",
  "strategy_path": "event_driven_backtest/backend/strategies/demo_buy_hold.py",
  "symbols": ["000001.SZ", "600000.SH"],
  "initial_cash": 1000000,
  "start_datetime": "2024-01-02 09:30:00",
  "end_datetime": "2024-03-29 15:00:00",
  "bar_frequency": "5m",
  "max_positions": 5,
  "slippage": 0.001,
  "commission": 0.0003,
  "stamp_duty": 0.001,
  "adjustment": "qfq",
  "match_mode": "next_open",
  "benchmark": "000300.SH"
}
```

示例命令：

```bash
curl -X POST 'http://127.0.0.1:8000/api/backtests' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "演示回测",
    "strategy_name": "demo_buy_hold",
    "strategy_type": "class",
    "strategy_path": "event_driven_backtest/backend/strategies/demo_buy_hold.py",
    "symbols": ["000001.SZ", "600000.SH"],
    "initial_cash": 1000000,
    "start_datetime": "2024-01-02 09:30:00",
    "end_datetime": "2024-03-29 15:00:00",
    "bar_frequency": "5m",
    "max_positions": 5,
    "slippage": 0.001,
    "commission": 0.0003,
    "stamp_duty": 0.001,
    "adjustment": "qfq",
    "match_mode": "next_open",
    "benchmark": "000300.SH"
  }'
```

### 7.2 查询接口

| 接口 | 说明 |
|---|---|
| `GET /api/strategies` | 获取策略目录中的可选策略文件 |
| `GET /api/stock-pools` | 获取股票池列表 |
| `POST /api/stock-pools` | 创建股票池 |
| `GET /api/stock-pools/{pool_id}` | 获取股票池详情 |
| `PUT /api/stock-pools/{pool_id}` | 更新股票池 |
| `DELETE /api/stock-pools/{pool_id}` | 删除股票池 |
| `GET /api/backtests` | 获取回测列表 |
| `GET /api/backtests/{run_id}` | 获取回测摘要 |
| `GET /api/backtests/{run_id}/equity` | 获取策略净值曲线 |
| `GET /api/backtests/{run_id}/benchmark` | 获取基准收益曲线 |
| `GET /api/backtests/{run_id}/drawdown` | 获取回撤曲线 |
| `GET /api/backtests/{run_id}/trades` | 获取成交记录，支持 `start_date` / `end_date` / `granularity=raw|day` |
| `GET /api/backtests/{run_id}/positions` | 获取持仓快照，支持 `start_date` / `end_date` / `granularity=raw|day` |
| `GET /api/backtests/{run_id}/logs` | 获取运行日志 |
| `GET /api/backtests/{run_id}/stream` | 通过 SSE 订阅运行中回测的实时进度 |

### 7.3 异步创建与实时进度

当前 `POST /api/backtests` 会立即返回：

- `run_id`
- `status = RUNNING`

真正的回测执行会在后端后台线程中继续进行。当前端进入历史回测详情页后，如果任务仍处于 `RUNNING`，会自动通过 `GET /api/backtests/{run_id}/stream` 建立 SSE 连接，并实时接收：

- `snapshot`：连接建立后的当前内存快照
- `status`：任务状态变更
- `log`：策略日志增量
- `equity`：收益曲线增量
- `trade`：成交增量
- `position`：持仓快照增量
- `complete`：任务完成事件

后端入口：`/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/api/server.py`

## 8. 策略接入方式

当前支持两种策略接入方式。

### 8.1 类式策略

示例文件：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/strategies/demo_buy_hold.py`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/strategies/minute_sma_5_20.py`

其中 `minute_sma_5_20.py` 是当前用于验证完整链路的最简分钟级双均线策略：

- 使用 `SMA(5)` 与 `SMA(20)`
- 快线上穿慢线时全仓买入
- 快线下穿慢线时全仓卖出
- 买入数量按 A 股 `100` 股整数倍取整

最小结构示意：

```python
class MyStrategy:
    name = 'my_strategy'

    def on_bar(self, context, bars):
        return []
```

### 8.2 脚本式策略

脚本式策略由 `strategy_sdk/script_adapter.py` 负责适配，适合把研究阶段的逻辑快速迁移到回测引擎中。

### 8.3 策略加载层

相关代码位于：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/strategy_sdk/loader.py`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/strategy_sdk/class_adapter.py`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/strategy_sdk/script_adapter.py`

## 9. 通达信函数支持

策略中如需使用通达信风格指标函数，可从以下模块接入：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/tdx/indicators.py`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/tdx/runtime.py`

这部分设计目标是降低把通达信选股逻辑迁移到 Python 回测环境中的成本。

## 10. 结果持久化

回测完成后，结果会同时写入数据库与文件系统。

### 10.1 MySQL

数据库中当前主要包含：

- `backtest_runs`
- `backtest_metrics`
- `backtest_artifacts`

同库中股票池相关表：

- `stock_pool`
- `stock_pool_symbol`

### 10.2 文件产物

默认结果目录：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/backend/storage/results/`

每次回测会生成一个独立目录，常见产物包括：

- `summary.json`
- `logs.jsonl`
- `equity.parquet`
- `benchmark_curve.parquet`
- `drawdown_curve.parquet`
- `trades.parquet`
- `positions.parquet`

### 10.3 历史 SQLite 元数据迁移

如果你此前有 `backtests.db` 历史数据，可执行：

```bash
cd /Users/jinziguan/Desktop/quantitativeTradeProject
source /Users/jinziguan/.virtualenvs/Python_Calculation/bin/activate
python -m event_driven_backtest.backend.storage.migrate_sqlite_to_mysql --sqlite-path event_driven_backtest/backend/storage/backtests.db
```

该脚本会把以下表的数据 upsert 到 MySQL：

- `backtest_runs`
- `backtest_metrics`
- `backtest_artifacts`

## 11. 前端页面说明

当前前端已重构为工作台式布局：

- 左侧固定历史回测列表
- 应用默认进入 `历史回测` 视图，避免首屏就请求策略目录
- 右侧顶部双 Tab：`历史回测` / `新建回测`
- 独立股票池管理页
- 新建回测表单页（仅在切换到该页时加载策略目录，支持选择股票池、时间选择器与 select 控件）
- 历史回测详情页（运行中自动实时同步）

详情页当前已支持展示：

- 核心绩效指标摘要
- 运行中实时同步的收益曲线与日志
- 策略收益、基准收益、超额收益切换
- 时间范围快捷切换与起止日期筛选
- 普通轴 / 对数轴切换
- 最大回撤区间高亮
- 独立回撤图
- 默认折叠的交易记录查询区（支持原始 / 按天聚合，展开后需手动点击“查询”）
- 默认折叠的持仓快照查询区（支持原始 / 按天聚合，展开后需手动点击“查询”）
- 日志面板

前端关键页面文件：

- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/frontend/src/pages/BacktestCreatePage.tsx`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/frontend/src/pages/BacktestListPage.tsx`
- `/Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/frontend/src/pages/BacktestDetailPage.tsx`

## 12. 测试与构建

### 12.1 后端测试

```bash
cd /Users/jinziguan/Desktop/quantitativeTradeProject
source /Users/jinziguan/.virtualenvs/Python_Calculation/bin/activate
python -m unittest discover event_driven_backtest/backend/tests
```

### 12.2 前端构建

```bash
cd /Users/jinziguan/Desktop/quantitativeTradeProject/event_driven_backtest/frontend
npm run build
```

## 13. 当前已知限制

- 首版只覆盖 A 股股票多头场景
- 当前分钟线读取默认依赖 ClickHouse 的 `stock_bar_1m` 表
- 当前证券元数据读取默认依赖 MySQL 的 `stock_symbol` 表
- 当前回测元数据默认依赖 MySQL 的 `backtest_runs/backtest_metrics/backtest_artifacts` 表
- `qfq` 暂未接入独立复权因子，当前回退为原始价格
- `hfq` 后复权尚未实现
- 更多撮合细节、风控规则和分析指标仍可继续扩展

## 14. 推荐的日常使用流程

```text
1. 启动后端 API
2. 用 Swagger 或前端创建回测任务
3. 查询 run_id 对应结果
4. 在详情页查看收益、基准、回撤、成交与持仓
5. 基于 strategy_sdk 与 tdx 模块继续迭代策略
```

如果你接下来还想继续完善，我建议优先做下面几项：

- 给 Vite 增加 `/api` 代理，打通本地前后端联调
- 增加更多示例策略
- 增加超额收益曲线与更多绩效指标
- 增加更接近聚宽体验的图表交互能力
