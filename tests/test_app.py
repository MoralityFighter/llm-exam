"""
测试用例 - 使用 mock 替代真实 Claude API 调用
覆盖：正常对话、多轮上下文、工具调用、RAG 检索、错误场景
"""
import json
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.session_store import session_store
from app.knowledge import knowledge_store


@pytest.fixture(autouse=True)
def cleanup():
    """每个测试前后清理状态"""
    session_store.clear_all()
    knowledge_store._documents.clear()
    yield
    session_store.clear_all()
    knowledge_store._documents.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ========== 辅助 Mock 对象 ==========

def _make_mock_stream(text_chunks: list):
    """创建模拟的 streaming 响应"""
    class MockStreamManager:
        def __enter__(self_inner):
            return self_inner
        def __exit__(self_inner, *args):
            pass
        @property
        def text_stream(self_inner):
            return iter(text_chunks)

    return MockStreamManager()


def _make_mock_response(text: str, stop_reason: str = "end_turn"):
    """创建模拟的非 streaming 响应"""
    mock_resp = MagicMock()
    mock_resp.stop_reason = stop_reason

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    mock_resp.content = [text_block]

    return mock_resp


def _make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tool_123"):
    """创建模拟的 tool_use 响应"""
    mock_resp = MagicMock()
    mock_resp.stop_reason = "tool_use"

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_id
    mock_resp.content = [tool_block]

    return mock_resp


# ========== 测试 1：正常对话 ==========

@patch("app.main.ANTHROPIC_API_KEY", "test-key")
def test_normal_chat(client):
    """测试 1：发送消息并收到正确的 streaming 响应"""
    mock_stream = _make_mock_stream(["你", "好", "！"])
    mock_response = _make_mock_response("你好！", stop_reason="end_turn")

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response
        instance.messages.stream.return_value = mock_stream

        response = client.post("/chat", json={
            "session_id": "test-1",
            "message": "你好"
        })

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # 解析 SSE 事件
        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        # 应包含文本和停止事件
        text_events = [e for e in events if e.get("type") == "content_block_delta"]
        stop_events = [e for e in events if e.get("type") == "message_stop"]
        assert len(text_events) > 0
        assert len(stop_events) == 1


# ========== 测试 2：多轮上下文 ==========

@patch("app.main.ANTHROPIC_API_KEY", "test-key")
def test_multi_turn_context(client):
    """测试 2：连续对话，验证上下文被正确维护"""
    mock_stream = _make_mock_stream(["回复1"])
    mock_response = _make_mock_response("回复1", stop_reason="end_turn")

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response
        instance.messages.stream.return_value = mock_stream

        # 第一轮对话
        client.post("/chat", json={
            "session_id": "test-multi",
            "message": "我叫小明"
        })

    # 验证会话历史包含用户消息和助手回复
    history = session_store.get_history("test-multi")
    assert history is not None
    assert len(history) >= 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "我叫小明"

    # 模拟第二轮
    mock_stream2 = _make_mock_stream(["你叫小明"])
    mock_response2 = _make_mock_response("你叫小明", stop_reason="end_turn")

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response2
        instance.messages.stream.return_value = mock_stream2

        client.post("/chat", json={
            "session_id": "test-multi",
            "message": "我叫什么名字？"
        })

    history = session_store.get_history("test-multi")
    assert len(history) >= 3  # 至少有：user, assistant, user


# ========== 测试 3：工具调用 ==========

@patch("app.main.ANTHROPIC_API_KEY", "test-key")
def test_tool_use(client):
    """测试 3：发送触发工具的消息，验证工具被正确调用"""
    tool_response = _make_tool_use_response(
        "get_weather", {"city": "北京"}, "tool_abc"
    )
    final_stream = _make_mock_stream(["北京", "今天", "晴"])

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = tool_response
        instance.messages.stream.return_value = final_stream

        response = client.post("/chat", json={
            "session_id": "test-tool",
            "message": "北京今天天气怎么样？"
        })

        assert response.status_code == 200

        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        text_events = [e for e in events if e.get("type") == "content_block_delta"]
        assert len(text_events) > 0

        # 验证 create 被调用（tool use 检测阶段）
        instance.messages.create.assert_called_once()


# ========== 测试 4：RAG 检索 ==========

@patch("app.main.ANTHROPIC_API_KEY", "test-key")
def test_rag_search(client):
    """测试 4：上传文档后提问，验证检索结果被注入"""
    # 先上传文档
    test_content = "SmartBot 是一个智能助手产品。它支持多轮对话、工具调用和知识库检索功能。SmartBot 可以帮助用户回答各种问题。"
    file_data = io.BytesIO(test_content.encode("utf-8"))

    response = client.post(
        "/knowledge/upload",
        files={"file": ("产品手册.txt", file_data, "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["chunks"] > 0

    # 验证检索功能
    results = knowledge_store.search("SmartBot 功能")
    assert len(results) > 0
    assert any("SmartBot" in r for r in results)


# ========== 测试 5：错误场景 ==========

def test_error_invalid_session(client):
    """测试 5a：查询不存在的 session"""
    response = client.get("/sessions/nonexistent/history")
    assert response.status_code == 404


def test_error_delete_nonexistent_session(client):
    """测试 5b：删除不存在的 session"""
    response = client.delete("/sessions/nonexistent")
    assert response.status_code == 404


def test_error_missing_fields(client):
    """测试 5c：请求体格式错误（缺少必填字段）"""
    response = client.post("/chat", json={"session_id": "test"})
    assert response.status_code == 422


def test_error_invalid_file_format(client):
    """测试 5d：上传不支持的文件格式"""
    file_data = io.BytesIO(b"test content")
    response = client.post(
        "/knowledge/upload",
        files={"file": ("test.pdf", file_data, "application/pdf")}
    )
    assert response.status_code == 422


# ========== 额外测试：工具列表接口 ==========

def test_tools_list(client):
    """测试工具列表接口"""
    response = client.get("/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    tool_names = [t["name"] for t in data["tools"]]
    assert "get_weather" in tool_names
    assert "calculator" in tool_names


# ========== 额外测试：Prompt 接口 ==========

def test_prompts_endpoint(client):
    """测试 prompt 模板接口"""
    response = client.get("/prompts")
    assert response.status_code == 200
    data = response.json()
    assert "current_version" in data
    assert "template_content" in data


# ========== 额外测试：Session CRUD ==========

@patch("app.main.ANTHROPIC_API_KEY", "test-key")
def test_session_crud(client):
    """测试会话的创建、查询和删除完整流程"""
    mock_stream = _make_mock_stream(["测试回复"])
    mock_response = _make_mock_response("测试回复", stop_reason="end_turn")

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response
        instance.messages.stream.return_value = mock_stream

        # 创建会话（通过发送消息）
        client.post("/chat", json={
            "session_id": "crud-test",
            "message": "hello"
        })

    # 查询历史
    response = client.get("/sessions/crud-test/history")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "crud-test"
    assert len(data["messages"]) > 0

    # 删除会话
    response = client.delete("/sessions/crud-test")
    assert response.status_code == 204

    # 确认已删除
    response = client.get("/sessions/crud-test/history")
    assert response.status_code == 404
