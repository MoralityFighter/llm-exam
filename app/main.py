"""
LLM 应用开发实战 - 主应用入口
基于 FastAPI + Claude API 的多轮对话服务
"""
import json
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import anthropic

from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, API_TIMEOUT
from app.session_store import session_store
from app.tools import TOOL_DEFINITIONS, execute_tool, get_tools_list
from app.knowledge import knowledge_store
from app.prompt_manager import render_prompt, get_current_prompt_info

# ========== FastAPI App ==========

app = FastAPI(
    title="SmartBot API",
    description="基于 Claude API 的多轮对话服务，支持 Tool Use 和 RAG",
    version="1.0.0",
)


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., description="用户消息")
    use_knowledge: Optional[bool] = Field(False, description="是否使用知识库 RAG 检索")


class HistoryResponse(BaseModel):
    session_id: str
    messages: list


class UploadResponse(BaseModel):
    filename: str
    chunks: int
    status: str


# ========== 辅助函数 ==========

def _get_claude_client() -> anthropic.Anthropic:
    """获取 Claude API 客户端"""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API Key 未配置，请设置 ANTHROPIC_API_KEY 环境变量"
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _build_system_prompt(use_knowledge: bool, query: str = "") -> str:
    """构建 system prompt"""
    knowledge_context = ""
    if use_knowledge and knowledge_store.has_documents():
        results = knowledge_store.search(query, top_k=3)
        if results:
            parts = []
            for i, chunk in enumerate(results, 1):
                parts.append(f"[{i}] {chunk}")
            knowledge_context = "\n".join(parts)

    return render_prompt(knowledge_context=knowledge_context)


# ========== 第一阶段：多轮对话接口 ==========

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    多轮对话接口 (SSE Streaming)
    支持 Tool Use 和 RAG
    """
    client = _get_claude_client()

    # 记录用户消息
    session_store.add_message(request.session_id, "user", request.message)

    # 获取会话历史
    history = session_store.get_history(request.session_id)

    # 构建 system prompt
    system_prompt = _build_system_prompt(request.use_knowledge, request.message)

    # 构建消息列表（排除最新的，因为已经在 history 里了）
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    async def generate():
        """SSE 流式生成器"""
        try:
            # 第一次调用 Claude API（可能触发 tool use）
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                timeout=API_TIMEOUT,
            )

            # 检查是否需要工具调用
            if response.stop_reason == "tool_use":
                # 处理 Tool Use 流程
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id

                        # 执行工具
                        result = execute_tool(tool_name, tool_input)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                # 将工具调用和结果加入消息历史
                tool_messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]

                # 第二次调用 Claude，带上工具结果，使用 streaming
                with client.messages.stream(
                    model=CLAUDE_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=tool_messages,
                    tools=TOOL_DEFINITIONS,
                    timeout=API_TIMEOUT,
                ) as stream:
                    full_text = ""
                    for text in stream.text_stream:
                        full_text += text
                        data = json.dumps(
                            {"type": "content_block_delta", "text": text},
                            ensure_ascii=False
                        )
                        yield f"data: {data}\n\n"

                    # 记录助手完整回复
                    session_store.add_message(
                        request.session_id, "assistant", full_text
                    )

            else:
                # 没有工具调用，直接 streaming 返回
                # 重新发起 streaming 请求
                with client.messages.stream(
                    model=CLAUDE_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    timeout=API_TIMEOUT,
                ) as stream:
                    full_text = ""
                    for text in stream.text_stream:
                        full_text += text
                        data = json.dumps(
                            {"type": "content_block_delta", "text": text},
                            ensure_ascii=False
                        )
                        yield f"data: {data}\n\n"

                    # 记录助手完整回复
                    session_store.add_message(
                        request.session_id, "assistant", full_text
                    )

            # 发送结束标记
            yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"

        except anthropic.AuthenticationError:
            error_data = json.dumps({
                "type": "error",
                "error": "API Key 无效，请检查 ANTHROPIC_API_KEY 配置"
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        except anthropic.APITimeoutError:
            error_data = json.dumps({
                "type": "error",
                "error": "Claude API 调用超时，请稍后重试"
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        except anthropic.APIError as e:
            error_data = json.dumps({
                "type": "error",
                "error": f"Claude API 调用异常: {str(e)}"
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ========== 会话管理接口 ==========

@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """获取会话历史"""
    history = session_store.get_history(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return HistoryResponse(session_id=session_id, messages=history)


@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """删除会话"""
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return None


# ========== Tool Use 接口 ==========

@app.get("/tools")
async def list_tools():
    """获取可用工具列表"""
    return {"tools": get_tools_list()}


# ========== RAG 知识库接口 ==========

@app.post("/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    """上传知识文件（支持 .txt / .md）"""
    # 验证文件格式
    if not file.filename:
        raise HTTPException(status_code=422, detail="文件名不能为空")

    if not (file.filename.endswith(".txt") or file.filename.endswith(".md")):
        raise HTTPException(status_code=422, detail="仅支持 .txt 和 .md 格式文件")

    # 读取文件内容
    content = await file.read()
    text = content.decode("utf-8")

    if not text.strip():
        raise HTTPException(status_code=422, detail="文件内容为空")

    # 分块并存储
    chunk_count = knowledge_store.upload(file.filename, text)

    return UploadResponse(
        filename=file.filename,
        chunks=chunk_count,
        status="success"
    )


# ========== Prompt 管理接口 ==========

@app.get("/prompts")
async def get_prompts():
    """获取当前 prompt 模板信息"""
    return get_current_prompt_info()


# ========== 健康检查 ==========

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "api_key_configured": bool(ANTHROPIC_API_KEY),
        "knowledge_base": knowledge_store.get_stats(),
    }
