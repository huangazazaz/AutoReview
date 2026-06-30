# AI 策略页面对话式改造设计

## 概述

将 AI 策略页面从"单次生成"模式升级为真正的多轮 GPT 对话体验。用户可以在生成策略后继续与 AI 交互修改策略参数和逻辑，每次修改自动运行回测。

## 需求背景

当前 AI 策略页面存在以下问题：

1. **伪对话**——界面看起来像聊天，但每次发送都是独立的 API 调用，AI 没有上下文记忆
2. **无法二次修改**——生成策略后不能对 AI 说"把止损改成 3%"，必须重新描述整个策略
3. **回测按钮误导**——「🔄 重新回测」按钮实际调用 `send()`，等于重新生成而非基于已有策略修改
4. **无持久化**——刷新页面对话历史丢失

## 需求决策

| 需求项 | 决策 |
|--------|------|
| 对话方式 | 真正的多轮上下文感知 |
| 修改类型 | 参数微调 + 逻辑增删，AI 自主判断用户意图 |
| 历史持久化 | 跨页面刷新保留 |
| 回测触发 | 每次 AI 修改策略代码后自动回测 |
| 优化范围 | 仅 AI Strategy 页面 |

---

## 一、整体架构

采用**混合方案**：后端内存会话管理 + 前端 localStorage 存储 session_id。

```
┌──────────┐    POST /ai/chat     ┌──────────────┐    messages[]    ┌───────────┐
│  前端     │ ──────────────────► │  FastAPI      │ ──────────────► │ DeepSeek  │
│ React    │ ◄────────────────── │  Server       │ ◄────────────── │ API       │
│          │    ChatResponse      │              │   JSON response │           │
└──────────┘                      │              │                  └───────────┘
                                  │  ┌─────────┐ │
                                  │  │Session  │ │    exec() + backtest
                                  │  │Store    │ │ ──────────────────► 动态加载策略
                                  │  │(内存)   │ │ ◄────────────────── 回测结果
                                  │  └─────────┘ │
                                  └──────────────┘
```

---

## 二、后端设计

### 2.1 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ai/chat` | 发送消息，自动创建/续用会话 |
| GET | `/ai/chat/{session_id}` | 获取会话完整历史 |
| DELETE | `/ai/chat/{session_id}` | 删除会话 |

### 2.2 POST /ai/chat

**Request:**
```json
{
  "session_id": "string|null",
  "prompt": "把止损改成3%",
  "symbol": "600522",
  "start": "2024-01-01",
  "end": "2024-12-31"
}
```

**Response:**
```json
{
  "session_id": "abc123",
  "message": {
    "role": "assistant",
    "content": "已将止损从5%修改为3%，回测结果已更新。",
    "timestamp": "2026-06-30T10:00:00"
  },
  "strategy": {
    "name": "ma_cross_v1",
    "display_name": "双均线交叉策略",
    "description": "5日线上穿20日线买入...",
    "python_code": "class MACross(Strategy): ...",
    "yaml_code": "name: ma_cross_v1\n...",
    "reasoning": "基于移动平均线交叉信号..."
  },
  "backtest": {
    "symbol": "600522",
    "return_pct": 12.5,
    "win_rate": 0.45,
    "sharpe_ratio": 0.8,
    "max_drawdown_pct": -8.2,
    "total_trades": 15
  }
}
```

### 2.3 GET /ai/chat/{session_id}

返回完整会话历史：

```json
{
  "session": {
    "session_id": "abc123",
    "title": "做一个5日20日均线金叉策略",
    "created_at": "2026-06-30T09:00:00",
    "last_active": "2026-06-30T10:00:00",
    "message_count": 6
  },
  "messages": [
    { "role": "user", "content": "做一个5日20日均线金叉买入的策略...", "timestamp": "..." },
    { "role": "assistant", "content": "已生成策略...", "strategy": {...}, "backtest": {...}, "timestamp": "..." }
  ]
}
```

### 2.4 会话存储

- 实现：`Dict[str, Session]` + `threading.Lock` 内存存储
- Session 结构：
  ```python
  @dataclass
  class Session:
      session_id: str
      title: str
      created_at: datetime
      last_active: datetime
      messages: List[ChatMessage]
      current_strategy: Optional[dict]  # 最近生成的策略代码
  ```
- TTL：每 30 分钟清理超过 2 小时无活动的会话
- session_id：`uuid4().hex[:12]`

### 2.5 现有端点兼容

- `POST /ai/generate-strategy` 保留，内部创建临时会话并转发到 chat 逻辑
- `POST /strategies/save`、`DELETE /strategies/{name}` 不变

---

## 三、AI Prompt 设计

### 3.1 System Prompt

```
You are a quantitative trading strategy engineer in a multi-turn conversation.

You are helping a trader design, refine, and backtest A-share trading strategies.

CONTEXT: You may see previously generated strategy code in the conversation history.
When the user asks to modify something, find the latest strategy code and apply the changes.

RULES:
1. NEW strategy → action="generate": Create a complete Python strategy class + YAML config from scratch. Run backtest.
2. MODIFY strategy → action="modify": Take the latest strategy from conversation context, apply user's requested changes, output full modified code. Run backtest.
3. CHAT only → action="chat": User is asking a question or discussing ideas. Respond naturally in Chinese. Do NOT output strategy code.

Always respond in valid JSON:
{
  "action": "generate" | "modify" | "chat",
  "message": "你的自然语言回复",
  "strategy": {           // null for action=chat
    "name": "strategy_name",
    "display_name": "策略中文名",
    "description": "一句话描述",
    "python_code": "完整的Python策略类代码",
    "yaml_code": "完整的YAML配置",
    "reasoning": "设计思路"
  }
}
```

### 3.2 对话示例

```
User: 做一个5日20日均线金叉买入、死叉卖出的策略，止损5%
AI:   {"action":"generate", "message":"已生成双均线交叉策略...", "strategy":{...}, backtest:{...}}

User: 把止损改成3%
AI:   {"action":"modify", "message":"已将止损从5%修改为3%，回测已更新。", "strategy":{...}, backtest:{...}}

User: 这个策略适合震荡市吗？
AI:   {"action":"chat", "message":"这个趋势跟踪策略在震荡市中可能产生频繁假信号...", "strategy":null}
```

### 3.3 消息拼接策略

- 从会话中取最近 20 轮对话发给 DeepSeek
- `assistant` 消息中的 `python_code` 保留完整内容（AI 需要看到代码才能修改）
- 超出 20 轮的旧消息截断，但保留 system prompt 和最近策略代码摘要

---

## 四、前端设计

### 4.1 组件拆分

```
AIStrategy.tsx              # 主页面，组装布局 + 状态管理
├── ChatSessionList.tsx     # 左侧会话列表
├── ChatMessages.tsx        # 中间消息区（滚动容器）
│   └── ChatBubble.tsx      # 单条消息气泡
│       └── StrategyCard.tsx # 策略卡片（代码+回测指标+操作按钮）
└── ChatInput.tsx           # 底部输入区
```

### 4.2 布局

```
┌────────────┬────────────────────────────────────────────┐
│ 会话列表    │  顶部栏：[股票代码] [日期范围]              │
│            ├────────────────────────────────────────────┤
│ [+ 新会话] │  消息区                                     │
│            │  ┌──────────────────────────────────────┐  │
│ 会话 1  ◄  │  │ user: 做一个均线金叉策略               │  │
│ 会话 2     │  │ ai: 已生成策略 + [回测卡片] [代码区]   │  │
│            │  │ user: 把均线改成10日和30日              │  │
│            │  │ ai: 已修改 + [新回测卡片]              │  │
│            │  └──────────────────────────────────────┘  │
│            ├────────────────────────────────────────────┤
│            │ [输入框]                          [发送]   │
└────────────┴────────────────────────────────────────────┘
```

### 4.3 新增 API 方法（`web/src/api/client.ts`）

```typescript
chat: (params: {
  session_id?: string
  prompt: string
  symbol?: string
  start?: string
  end?: string
}) => post<ChatResponse>('/ai/chat', params),

getChatHistory: (sessionId: string) =>
  get<ChatHistoryResponse>(`/ai/chat/${sessionId}`),

deleteChat: (sessionId: string) =>
  del<{ ok: boolean }>(`/ai/chat/${sessionId}`),
```

### 4.4 状态管理

```typescript
// AIStrategy.tsx 核心状态
const [sessions, setSessions] = useState<ChatSession[]>([])
const [activeSessionId, setActiveSessionId] = useState<string>()
const [messages, setMessages] = useState<ChatMessage[]>([])
const [sending, setSending] = useState(false)
const [symbol, setSymbol] = useState('600522')
const [startDate, setStartDate] = useState('')
const [endDate, setEndDate] = useState('')

// 持久化
// - activeSessionId 存入 localStorage
// - 消息列表通过 GET /ai/chat/{id} 从后端恢复
```

### 4.5 关键交互

1. **首次进入**：读 localStorage `activeSessionId` → `GET /ai/chat/{id}` 恢复历史
2. **发送消息**：`POST /ai/chat` → 追加消息 + 自动渲染回测结果
3. **新建会话**：清空 `activeSessionId`，下次发送时后端自动创建
4. **切换会话**：点击左侧会话 → `GET /ai/chat/{id}` → 切换消息列表
5. **保存策略**：复用现有 `saveStrategy`，针对当前消息中的策略代码
6. **删除会话**：`DELETE /ai/chat/{id}`，从列表移除
7. **自动回测**：后端在每次 `action=generate|modify` 时自动运行，前端直接展示结果

---

## 五、类型定义（新增/变更）

### 5.1 TypeScript（`web/src/types/index.ts` 追加）

```typescript
// ---- AI 多轮对话 ----

export interface ChatRequest {
  session_id?: string
  prompt: string
  symbol?: string
  start?: string
  end?: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  strategy?: StrategyResult
  backtest?: AIStrategyBacktest
}

export interface StrategyResult {
  name: string
  display_name: string
  description: string
  python_code: string
  yaml_code: string
  reasoning: string
}

export interface ChatResponse {
  session_id: string
  message: {
    role: 'assistant'
    content: string
    timestamp: string
  }
  strategy?: StrategyResult
  backtest?: AIStrategyBacktest
}

export interface ChatSession {
  session_id: string
  title: string
  created_at: string
  last_active: string
  message_count: number
}

export interface ChatHistoryResponse {
  session: ChatSession
  messages: ChatMessage[]
}
```

### 5.2 Python（`autotrade/api/server.py` 追加）

```python
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    prompt: str
    symbol: str = "600522"
    start: Optional[str] = None
    end: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str
    strategy: Optional[dict] = None
    backtest: Optional[dict] = None

class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessage
    strategy: Optional[dict] = None
    backtest: Optional[dict] = None

class ChatHistoryResponse(BaseModel):
    session: dict
    messages: list[ChatMessage]
```

---

## 六、实现要点

### 6.1 修改顺序

1. **后端先行**：新增 chat 端点 + 会话管理 + Prompt 升级
2. **类型定义**：同步更新 TypeScript 类型
3. **API 客户端**：新增 chat/getChatHistory/deleteChat 方法
4. **前端重构**：拆分组件 + 实现多轮对话交互
5. **兼容验证**：确保现有 `generateStrategy` 仍可正常工作

### 6.2 风险点

| 风险 | 缓解措施 |
|------|----------|
| 长对话 token 超限 | 截断 20 轮 + 压缩策略代码 |
| 内存会话丢失 | 初期可接受，后续升级文件持久化 |
| AI 解析失败 | 保留 `raw` 字段兜底，错误消息友好提示 |
| 并发安全 | `threading.Lock` 保护 SessionStore |

### 6.3 不在此次范围

- 会话搜索/过滤
- 导出对话为 PDF/Markdown
- 多用户会话隔离
- WebSocket 流式输出（使用现有 loading 动画替代）
- 其他页面（Dashboard、Analyze、Backtest 等）的优化
