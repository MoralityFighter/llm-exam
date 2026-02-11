"""Prompt 模板管理模块"""
import os
import re
from typing import Dict, Optional

from app.config import PROMPT_VERSION


PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def _load_template(version: str) -> Optional[str]:
    """加载指定版本的模板文件"""
    filepath = os.path.join(PROMPTS_DIR, f"{version}.txt")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def render_prompt(
    knowledge_context: str = "",
    tool_list: str = "",
    version: str = None,
) -> str:
    """
    渲染 prompt 模板，替换模板变量
    支持 {{variable}} 和 {{if variable}}...{{/if}} 语法
    """
    version = version or PROMPT_VERSION
    template = _load_template(version)

    if template is None:
        # 如果找不到模板，使用内置默认
        template = "你是一个智能助手，名叫 SmartBot。请用简洁专业的语言回答用户问题。"

    # 处理条件块 {{if variable}}...{{/if}}
    def replace_conditional(match):
        var_name = match.group(1)
        block_content = match.group(2)
        # 根据变量是否有值来决定是否渲染
        values = {
            "knowledge_context": knowledge_context,
            "tool_list": tool_list,
        }
        if values.get(var_name, "").strip():
            # 替换块内的变量
            result = block_content
            for k, v in values.items():
                result = result.replace(f"{{{{{k}}}}}", v)
            return result
        return ""

    template = re.sub(
        r'\{\{if\s+(\w+)\}\}(.*?)\{\{/if\}\}',
        replace_conditional,
        template,
        flags=re.DOTALL
    )

    # 替换剩余的简单变量
    template = template.replace("{{knowledge_context}}", knowledge_context)
    template = template.replace("{{tool_list}}", tool_list)

    return template.strip()


def get_current_prompt_info() -> dict:
    """获取当前 prompt 模板的信息"""
    version = PROMPT_VERSION
    template = _load_template(version)

    # 列出所有可用的模板
    available = []
    if os.path.exists(PROMPTS_DIR):
        for f in os.listdir(PROMPTS_DIR):
            if f.endswith(".txt"):
                available.append(f.replace(".txt", ""))

    return {
        "current_version": version,
        "template_content": template or "(模板文件未找到，使用内置默认)",
        "available_versions": available,
    }
