"""应用配置模块"""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1_default")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
