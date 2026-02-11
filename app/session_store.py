"""会话存储模块 - 基于内存的会话管理"""
from typing import Dict, List, Optional


class SessionStore:
    """内存中的会话存储"""

    def __init__(self):
        self._sessions: Dict[str, List[dict]] = {}

    def get_history(self, session_id: str) -> Optional[List[dict]]:
        """获取会话历史，不存在返回 None"""
        if session_id not in self._sessions:
            return None
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """添加消息到会话历史"""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append({"role": role, "content": content})

    def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return session_id in self._sessions

    def delete(self, session_id: str) -> bool:
        """删除会话，返回是否成功"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def clear_all(self):
        """清除所有会话"""
        self._sessions.clear()


# 全局会话存储实例
session_store = SessionStore()
