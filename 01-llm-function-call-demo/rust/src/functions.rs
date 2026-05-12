use chrono::Local;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FunctionDefinition {
    pub name: String,
    pub description: String,
    pub parameters: Value,
}

// 获取天气信息（模拟）
pub fn get_weather(city: &str, unit: Option<&str>) -> String {
    let unit = unit.unwrap_or("celsius");

    let weather_data: HashMap<&str, HashMap<&str, Value>> = [
        (
            "北京",
            [
                ("condition", json!("晴天")),
                ("temp_c", json!(25)),
                ("temp_f", json!(77)),
                ("humidity", json!(45)),
            ]
            .iter()
            .cloned()
            .collect(),
        ),
        (
            "上海",
            [
                ("condition", json!("多云")),
                ("temp_c", json!(28)),
                ("temp_f", json!(82)),
                ("humidity", json!(65)),
            ]
            .iter()
            .cloned()
            .collect(),
        ),
        (
            "深圳",
            [
                ("condition", json!("小雨")),
                ("temp_c", json!(30)),
                ("temp_f", json!(86)),
                ("humidity", json!(80)),
            ]
            .iter()
            .cloned()
            .collect(),
        ),
    ]
    .iter()
    .cloned()
    .collect();

    let city_data = weather_data.get(city).cloned().unwrap_or_else(|| {
        [
            ("condition", json!("数据不可用")),
            ("temp_c", json!(20)),
            ("temp_f", json!(68)),
            ("humidity", json!(50)),
        ]
        .iter()
        .cloned()
        .collect()
    });

    let (temp, temp_unit) = if unit == "celsius" {
        (city_data["temp_c"].as_i64().unwrap(), "°C")
    } else {
        (city_data["temp_f"].as_i64().unwrap(), "°F")
    };

    let result = json!({
        "city": city,
        "condition": city_data["condition"],
        "temperature": format!("{}{}", temp, temp_unit),
        "humidity": format!("{}%", city_data["humidity"]),
        "timestamp": Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
    });

    serde_json::to_string(&result).unwrap()
}

// 执行数学计算
pub fn calculate(operation: &str, a: f64, b: f64) -> String {
    let result: Value = match operation {
        "add" => json!(a + b),
        "subtract" => json!(a - b),
        "multiply" => json!(a * b),
        "divide" => {
            if b != 0.0 {
                json!(a / b)
            } else {
                json!("错误：除数不能为零")
            }
        }
        _ => json!("不支持的运算"),
    };

    let response = json!({
        "operation": operation,
        "operand_a": a,
        "operand_b": b,
        "result": result,
    });

    serde_json::to_string(&response).unwrap()
}

// 搜索数据库（模拟）
pub fn search_database(query: &str, category: Option<&str>) -> String {
    let category = category.unwrap_or("all");

    let database: HashMap<&str, Vec<Value>> = [
        (
            "products",
            vec![
                json!({"id": 1, "name": "笔记本电脑", "price": 5999}),
                json!({"id": 2, "name": "机械键盘", "price": 599}),
                json!({"id": 3, "name": "无线鼠标", "price": 199}),
            ],
        ),
        (
            "users",
            vec![
                json!({"id": 1, "name": "张三", "email": "zhangsan@example.com"}),
                json!({"id": 2, "name": "李四", "email": "lisi@example.com"}),
            ],
        ),
        (
            "orders",
            vec![
                json!({"id": 1001, "user": "张三", "product": "笔记本电脑", "status": "已发货"}),
                json!({"id": 1002, "user": "李四", "product": "机械键盘", "status": "处理中"}),
            ],
        ),
    ]
    .iter()
    .cloned()
    .collect();

    let mut results = Vec::new();
    let search_categories: Vec<&str> = if category == "all" {
        database.keys().copied().collect()
    } else {
        vec![category]
    };

    // 解析价格范围查询（如"价格500元以上"）
    let price_filter = parse_price_query(query);

    for cat in search_categories {
        if let Some(items) = database.get(cat) {
            for item in items {
                let mut matched = false;

                // 如果有价格过滤条件且是产品类别
                if let Some((min_price, max_price)) = price_filter {
                    if cat == "products" {
                        if let Some(price) = item.get("price").and_then(|p| p.as_i64()) {
                            matched = price >= min_price && price <= max_price;
                        }
                    }
                } else {
                    // 普通字符串搜索
                    let item_str = serde_json::to_string(item).unwrap();
                    matched = item_str.to_lowercase().contains(&query.to_lowercase());
                }

                if matched {
                    let mut item_copy = item.clone();
                    if let Some(obj) = item_copy.as_object_mut() {
                        obj.insert("category".to_string(), json!(cat));
                    }
                    results.push(item_copy);
                }
            }
        }
    }

    let response = json!({
        "query": query,
        "category": category,
        "results": results,
        "count": results.len(),
    });

    serde_json::to_string(&response).unwrap()
}

// 解析价格查询（返回 (min, max)）
fn parse_price_query(query: &str) -> Option<(i64, i64)> {
    let query_lower = query.to_lowercase();
    
    // 提取数字
    let numbers: Vec<i64> = query
        .chars()
        .filter(|c| c.is_numeric())
        .collect::<String>()
        .parse::<i64>()
        .ok()
        .into_iter()
        .collect();

    if numbers.is_empty() {
        return None;
    }

    let price = numbers[0];

    // 判断是"以上"还是"以下"
    if query_lower.contains("以上") || query_lower.contains("大于") || query_lower.contains(">") {
        Some((price, i64::MAX))
    } else if query_lower.contains("以下") || query_lower.contains("小于") || query_lower.contains("<") {
        Some((0, price))
    } else if query_lower.contains("价格") && numbers.len() == 1 {
        // 如果只提到"价格XXX"，默认查找该价格附近的（±100）
        Some((price - 100, price + 100))
    } else {
        None
    }
}

// 执行函数
pub fn execute_function(function_name: &str, arguments: &Value) -> String {
    match function_name {
        "get_weather" => {
            let city = arguments["city"].as_str().unwrap();
            let unit = arguments.get("unit").and_then(|v| v.as_str());
            get_weather(city, unit)
        }
        "calculate" => {
            let operation = arguments["operation"].as_str().unwrap();
            let a = arguments["a"].as_f64().unwrap();
            let b = arguments["b"].as_f64().unwrap();
            calculate(operation, a, b)
        }
        "search_database" => {
            let query = arguments["query"].as_str().unwrap();
            let category = arguments.get("category").and_then(|v| v.as_str());
            search_database(query, category)
        }
        _ => json!({"error": format!("未找到函数: {}", function_name)}).to_string(),
    }
}

// 函数定义列表
pub fn get_function_definitions() -> Vec<FunctionDefinition> {
    vec![
        FunctionDefinition {
            name: "get_weather".to_string(),
            description: "获取指定城市的天气信息".to_string(),
            parameters: json!({
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
            }),
        },
        FunctionDefinition {
            name: "calculate".to_string(),
            description: "执行数学运算".to_string(),
            parameters: json!({
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
            }),
        },
        FunctionDefinition {
            name: "search_database".to_string(),
            description: "搜索数据库".to_string(),
            parameters: json!({
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
            }),
        },
    ]
}
