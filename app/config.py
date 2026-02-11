"""应用配置模块"""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1_default")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
