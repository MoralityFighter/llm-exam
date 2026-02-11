"""Tool Use 工具定义与执行模块"""
import re
import math


# ========== 工具定义（给 Claude API 用的 schema） ==========

TOOL_DEFINITIONS = [
    {
        "name": "get_weather",
        "description": "查询指定城市的天气信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "要查询天气的城市名称"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculator",
        "description": "数学计算器，支持加减乘除和括号运算",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，如 2+3*4 或 (15+7)*3"
                }
            },
            "required": ["expression"]
        }
    }
]


# ========== Mock 天气数据 ==========

MOCK_WEATHER_DATA = {
    "北京": {"city": "北京", "temperature": "22°C", "condition": "晴"},
    "上海": {"city": "上海", "temperature": "26°C", "condition": "多云"},
    "广州": {"city": "广州", "temperature": "30°C", "condition": "阵雨"},
    "深圳": {"city": "深圳", "temperature": "29°C", "condition": "多云转晴"},
    "杭州": {"city": "杭州", "temperature": "24°C", "condition": "阴"},
    "成都": {"city": "成都", "temperature": "20°C", "condition": "小雨"},
}


def execute_get_weather(city: str) -> dict:
    """执行天气查询工具"""
    if city in MOCK_WEATHER_DATA:
        return MOCK_WEATHER_DATA[city]
    # 未知城市返回默认数据
    return {"city": city, "temperature": "25°C", "condition": "晴"}


def execute_calculator(expression: str) -> dict:
    """执行计算器工具 - 安全地计算数学表达式"""
    try:
        # 只允许数字、运算符和括号
        sanitized = expression.replace(" ", "")
        if not re.match(r'^[\d+\-*/().]+$', sanitized):
            return {"expression": expression, "error": "不支持的表达式格式"}

        result = eval(sanitized, {"__builtins__": {}}, {"math": math})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """根据工具名称分发执行"""
    if tool_name == "get_weather":
        return execute_get_weather(tool_input.get("city", ""))
    elif tool_name == "calculator":
        return execute_calculator(tool_input.get("expression", ""))
    else:
        return {"error": f"未知工具: {tool_name}"}


def get_tools_list() -> list:
    """返回工具列表（API 展示格式）"""
    tools = []
    for tool_def in TOOL_DEFINITIONS:
        params = {}
        schema = tool_def["input_schema"]
        required_fields = schema.get("required", [])
        for prop_name, prop_schema in schema.get("properties", {}).items():
            params[prop_name] = {
                "type": prop_schema.get("type", "string"),
                "required": prop_name in required_fields
            }
        tools.append({
            "name": tool_def["name"],
            "description": tool_def["description"],
            "parameters": params
        })
    return tools
