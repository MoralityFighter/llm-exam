"""Tool Use 工具定义与执行模块"""
import re
import math
import httpx


# ========== 工具定义（给 Claude API 用的 schema） ==========

TOOL_DEFINITIONS = [
    {
        "name": "get_weather",
        "description": "查询指定城市的实时天气信息",
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


# ========== 城市坐标映射（用于 Open-Meteo API） ==========

CITY_COORDINATES = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "成都": (30.5728, 104.0668),
    "武汉": (30.5928, 114.3055),
    "南京": (32.0603, 118.7969),
    "重庆": (29.4316, 106.9123),
    "西安": (34.3416, 108.9398),
    "长沙": (28.2282, 112.9388),
    "天津": (39.0842, 117.2010),
    "苏州": (31.2990, 120.5853),
    "郑州": (34.7466, 113.6253),
    "青岛": (36.0671, 120.3826),
    "大连": (38.9140, 121.6147),
    "厦门": (24.4798, 118.0894),
    "昆明": (25.0389, 102.7183),
    "哈尔滨": (45.8038, 126.5350),
    "沈阳": (41.8057, 123.4315),
    "拉萨": (29.6500, 91.1000),
    "乌鲁木齐": (43.8256, 87.6168),
    "香港": (22.3193, 114.1694),
    "台北": (25.0330, 121.5654),
    "东京": (35.6762, 139.6503),
    "首尔": (37.5665, 126.9780),
    "纽约": (40.7128, -74.0060),
    "伦敦": (51.5074, -0.1278),
    "巴黎": (48.8566, 2.3522),
}

# WMO 天气代码 → 中文描述
WMO_WEATHER_CODES = {
    0: "晴",
    1: "大部晴朗", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "大冻雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    77: "雪粒",
    80: "小阵雨", 81: "阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
}


def execute_get_weather(city: str) -> dict:
    """
    执行天气查询工具 - 使用 Open-Meteo API 获取真实天气数据
    Open-Meteo: 免费、无需 API Key
    """
    coords = CITY_COORDINATES.get(city)

    if not coords:
        # 尝试通过 Open-Meteo Geocoding API 查找城市
        coords = _geocode_city(city)

    if not coords:
        return {"city": city, "temperature": "未知", "condition": "未找到该城市"}

    lat, lon = coords

    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})
        temp = current.get("temperature_2m")
        weather_code = current.get("weather_code", 0)
        wind_speed = current.get("wind_speed_10m")
        humidity = current.get("relative_humidity_2m")

        condition = WMO_WEATHER_CODES.get(weather_code, "未知")

        result = {
            "city": city,
            "temperature": f"{temp}°C" if temp is not None else "未知",
            "condition": condition,
        }

        # 附加信息
        if wind_speed is not None:
            result["wind_speed"] = f"{wind_speed} km/h"
        if humidity is not None:
            result["humidity"] = f"{humidity}%"

        return result

    except Exception as e:
        # API 调用失败，返回错误信息
        return {"city": city, "temperature": "查询失败", "condition": f"API 错误: {str(e)}"}


def _geocode_city(city_name: str) -> tuple:
    """通过 Open-Meteo Geocoding API 根据城市名查找坐标"""
    try:
        response = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_name, "count": 1, "language": "zh"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if results:
            return (results[0]["latitude"], results[0]["longitude"])
    except Exception:
        pass
    return None


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
