# CLAUDE.md

## 项目概述
SmartBot API - 基于 Claude API 的多轮对话后端服务，支持 Tool Use 和 RAG 知识检索。

## 技术栈
- Python 3.9+
- FastAPI
- Anthropic Python SDK
- uvicorn

## 快速启动
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env  # 然后编辑 .env 填入 API Key

# 启动服务
uvicorn app.main:app --reload --port 8000
```

## 运行测试
```bash
# 运行全部测试（使用 mock，无需真实 API Key）
pytest tests/ -v

# 运行单个测试
pytest tests/test_app.py::test_normal_chat -v
```

## 项目结构
```
├── app/
│   ├── main.py           # FastAPI 主应用
│   ├── config.py          # 配置管理
│   ├── session_store.py   # 会话存储
│   ├── tools.py           # Tool Use 工具定义与执行
│   ├── knowledge.py       # RAG 知识库
│   └── prompt_manager.py  # Prompt 模板管理
├── prompts/               # Prompt 模板文件
├── tests/                 # 测试用例
├── requirements.txt
└── .env                   # 环境变量（不提交）
```

## 关键设计决策
- 会话存储使用内存（Dict），无需外部数据库
- RAG 检索使用 TF-IDF 关键词匹配
- Tool Use 中天气查询使用 Mock 数据
- Prompt 模板支持条件渲染和变量替换
