# SmartBot API

基于 Claude API 的多轮对话后端服务，支持 Streaming SSE、Tool Use 工具调用和 RAG 知识库检索。

## 项目简介

SmartBot API 是一个完整的 LLM 应用后端，提供以下能力：

- **多轮对话**：基于 session 的上下文管理，支持 SSE 流式响应
- **Tool Use**：集成天气查询和数学计算器工具，Claude 自动判断并调用
- **RAG 检索增强**：支持文档上传、分块、关键词检索，将知识注入对话上下文
- **Prompt 模板管理**：模板化的 system prompt，支持变量替换和版本切换

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| LLM API | Anthropic Claude API (SDK) |
| 语言 | Python 3.9+ |
| 测试 | pytest + mock |

## 快速启动

### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 Anthropic API Key
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

服务启动后访问 http://localhost:8000/docs 查看自动生成的 API 文档。

## API 接口文档

### POST /chat — 多轮对话（SSE Streaming）

**请求体：**
```json
{
  "session_id": "user-123",
  "message": "你好",
  "use_knowledge": false
}
```

**响应（SSE 流）：**
```
data: {"type": "content_block_delta", "text": "你"}
data: {"type": "content_block_delta", "text": "好"}
data: {"type": "content_block_delta", "text": "！"}
data: {"type": "message_stop"}
```

### GET /sessions/{session_id}/history — 查询会话历史

**响应：**
```json
{
  "session_id": "user-123",
  "messages": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的吗？"}
  ]
}
```

### DELETE /sessions/{session_id} — 删除会话

- 成功：`204 No Content`
- 会话不存在：`404`

### GET /tools — 查询可用工具列表

**响应：**
```json
{
  "tools": [
    {
      "name": "get_weather",
      "description": "查询指定城市的天气信息",
      "parameters": {
        "city": { "type": "string", "required": true }
      }
    },
    {
      "name": "calculator",
      "description": "数学计算器，支持加减乘除和括号运算",
      "parameters": {
        "expression": { "type": "string", "required": true }
      }
    }
  ]
}
```

### POST /knowledge/upload — 上传知识文件

**请求：** `multipart/form-data`，字段 `file`（支持 .txt / .md）

**响应：**
```json
{
  "filename": "产品手册.txt",
  "chunks": 12,
  "status": "success"
}
```

### GET /prompts — 查看当前 Prompt 模板

**响应：**
```json
{
  "current_version": "v1_default",
  "template_content": "你是一个智能助手...",
  "available_versions": ["v1_default", "v2_professional"]
}
```

### GET /health — 健康检查

**响应：**
```json
{
  "status": "ok",
  "api_key_configured": true,
  "knowledge_base": { "documents": 0, "total_chunks": 0, "filenames": [] }
}
```

## 错误处理

| 场景 | 状态码 | 说明 |
|------|--------|------|
| API Key 未配置 | 500 | 返回明确错误信息 |
| 请求体格式错误 | 422 | 缺少必填字段 |
| 会话不存在 | 404 | 查询/删除不存在的会话 |
| Claude API 超时 | 502 | API 调用超时或异常 |

## 架构简图

```
┌─────────────┐     HTTP/SSE      ┌──────────────────────────┐
│   Client    │ ◄──────────────► │     FastAPI Server        │
│  (前端/curl) │                  │                          │
└─────────────┘                  │  ┌────────────────────┐  │
                                 │  │   /chat (SSE)      │  │
                                 │  │   ├─ Session Store  │  │
                                 │  │   ├─ Tool Use       │──┼──► Claude API
                                 │  │   └─ RAG Inject     │  │
                                 │  ├────────────────────┤  │
                                 │  │   /knowledge       │  │
                                 │  │   └─ Upload + Chunk │  │
                                 │  ├────────────────────┤  │
                                 │  │   /tools           │  │
                                 │  ├────────────────────┤  │
                                 │  │   /prompts         │  │
                                 │  │   └─ Template Mgr   │  │
                                 │  └────────────────────┘  │
                                 │                          │
                                 │  ┌────────────────────┐  │
                                 │  │   In-Memory Store   │  │
                                 │  │  ├─ Sessions (dict) │  │
                                 │  │  └─ Knowledge (TF)  │  │
                                 │  └────────────────────┘  │
                                 └──────────────────────────┘
```

## 运行测试

```bash
# 运行全部测试（使用 mock，无需真实 API Key）
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_app.py -v
```

## 项目结构

```
llm-exam/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI 主应用，所有路由
│   ├── config.py           # 环境变量与配置
│   ├── session_store.py    # 内存会话管理
│   ├── tools.py            # Tool Use 工具定义与执行
│   ├── knowledge.py        # RAG 知识库（分块+检索）
│   └── prompt_manager.py   # Prompt 模板管理
├── prompts/
│   ├── v1_default.txt      # 默认 prompt 模板
│   └── v2_professional.txt # 专业版 prompt 模板
├── tests/
│   ├── __init__.py
│   └── test_app.py         # 完整测试用例
├── .env.example            # 环境变量示例
├── .gitignore
├── requirements.txt
├── CLAUDE.md               # Claude Code 项目说明
└── README.md               # 项目文档
```

---

> 使用 Claude Code 全程开发完成
