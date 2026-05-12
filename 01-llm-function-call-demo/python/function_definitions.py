"""
函数定义模块
"""

import json
from datetime import datetime


# ============ 函数实现 ============

def get_weather(city: str, unit: str = "celsius") -> str:
    """获取天气信息（模拟）"""
    weather_data = {
        "北京": {"condition": "晴天", "temp_c": 25, "temp_f": 77, "humidity": 45},
        "上海": {"condition": "多云", "temp_c": 28, "temp_f": 82, "humidity": 65},
        "深圳": {"condition": "小雨", "temp_c": 30, "temp_f": 86, "humidity": 80},
    }
    
    city_data = weather_data.get(city, {
        "condition": "数据不可用",
        "temp_c": 20,
        "temp_f": 68,
        "humidity": 50
    })
    
    temp = city_data["temp_c"] if unit == "celsius" else city_data["temp_f"]
    temp_unit = "°C" if unit == "celsius" else "°F"
    
    result = {
        "city": city,
        "condition": city_data["condition"],
        "temperature": f"{temp}{temp_unit}",
        "humidity": f"{city_data['humidity']}%",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return json.dumps(result, ensure_ascii=False)


def calculate(operation: str, a: float, b: float) -> str:
    """执行数学计算"""
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "错误：除数不能为零"
    }
    
    result = {
        "operation": operation,
        "operand_a": a,
        "operand_b": b,
        "result": operations.get(operation, "不支持的运算")
    }
    
    return json.dumps(result, ensure_ascii=False)


def search_database(query: str, category: str = "all") -> str:
    """搜索数据库（模拟）"""
    database = {
        "products": [
            {"id": 1, "name": "笔记本电脑", "price": 5999},
            {"id": 2, "name": "机械键盘", "price": 599},
            {"id": 3, "name": "无线鼠标", "price": 199},
        ],
        "users": [
            {"id": 1, "name": "张三", "email": "zhangsan@example.com"},
            {"id": 2, "name": "李四", "email": "lisi@example.com"},
        ],
        "orders": [
            {"id": 1001, "user": "张三", "product": "笔记本电脑", "status": "已发货"},
            {"id": 1002, "user": "李四", "product": "机械键盘", "status": "处理中"},
        ]
    }
    
    results = []
    search_categories = [category] if category != "all" else database.keys()
    
    # 解析价格范围查询
    price_filter = _parse_price_query(query)
    
    for cat in search_categories:
        if cat in database:
            for item in database[cat]:
                matched = False
                
                # 如果有价格过滤条件且是产品类别
                if price_filter and cat == "products":
                    min_price, max_price = price_filter
                    if "price" in item:
                        matched = min_price <= item["price"] <= max_price
                else:
                    # 普通字符串搜索
                    matched = query.lower() in str(item).lower()
                
                if matched:
                    results.append({**item, "category": cat})
    
    return json.dumps({
        "query": query,
        "category": category,
        "results": results,
        "count": len(results)
    }, ensure_ascii=False)


def _parse_price_query(query: str) -> tuple:
    """解析价格查询（返回 (min, max)）"""
    import re
    
    query_lower = query.lower()
    
    # 提取数字
    numbers = re.findall(r'\d+', query)
    if not numbers:
        return None
    
    price = int(numbers[0])
    
    # 判断是"以上"还是"以下"
    if any(word in query_lower for word in ["以上", "大于", ">"]):
        return (price, float('inf'))
    elif any(word in query_lower for word in ["以下", "小于", "<"]):
        return (0, price)
    elif "价格" in query_lower and len(numbers) == 1:
        # 如果只提到"价格XXX"，默认查找该价格附近的（±100）
        return (price - 100, price + 100)
    
    return None


# ============ 函数定义（JSON Schema）============

FUNCTION_DEFINITIONS = [
    {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如：北京、上海"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate",
        "description": "执行数学运算",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "运算类型"
                },
                "a": {
                    "type": "number",
                    "description": "第一个数"
                },
                "b": {
                    "type": "number",
                    "description": "第二个数"
                }
            },
            "required": ["operation", "a", "b"]
        }
    },
    {
        "name": "search_database",
        "description": "搜索数据库",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "category": {
                    "type": "string",
                    "enum": ["all", "products", "users", "orders"],
                    "description": "搜索类别"
                }
            },
            "required": ["query"]
        }
    }
]


# ============ 函数调度器 ============

def execute_function(function_name: str, arguments: dict) -> str:
    """执行函数"""
    available_functions = {
        "get_weather": get_weather,
        "calculate": calculate,
        "search_database": search_database
    }
    
    function = available_functions.get(function_name)
    
    if function is None:
        return json.dumps({"error": f"未找到函数: {function_name}"}, ensure_ascii=False)
    
    try:
        result = function(**arguments)
        return result
    except Exception as e:
        return json.dumps({"error": f"函数执行错误: {str(e)}"}, ensure_ascii=False)
