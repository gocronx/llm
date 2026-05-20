//! tools.rs —— 工具注册表：函数本体 + JSON Schema 配在一起。
//! 加新工具：写一个 `fn xxx_tool() -> Tool`，把它加进 `all()`。client/main 不用改。

use serde_json::{json, Value};

pub struct Tool {
    pub name: &'static str,
    pub schema: Value, // OpenAI function 字段（不含 type: function 外壳）
    pub call: fn(Value) -> Value,
}

pub fn all() -> Vec<Tool> {
    vec![weather(), calculate(), search_products()]
}

/// 返回给 LLM 的 tools 字段。
pub fn schemas() -> Vec<Value> {
    all()
        .into_iter()
        .map(|t| json!({"type": "function", "function": t.schema}))
        .collect()
}

/// 执行一次工具调用，返回 JSON 字符串（OpenAI tool message 要的格式）。
pub fn call(name: &str, args_json: &str) -> String {
    for t in all() {
        if t.name == name {
            let args: Value = serde_json::from_str(args_json).unwrap_or(json!({}));
            return (t.call)(args).to_string();
        }
    }
    json!({"error": format!("unknown tool: {name}")}).to_string()
}

// ---- 三个示例工具 ----

fn weather() -> Tool {
    Tool {
        name: "get_weather",
        schema: json!({
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如：北京"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["city"]
            }
        }),
        call: |args| {
            let city = args["city"].as_str().unwrap_or("");
            let unit = args["unit"].as_str().unwrap_or("celsius");
            let (c, cond) = match city {
                "北京" => (25.0, "晴"),
                "上海" => (28.0, "多云"),
                "深圳" => (30.0, "小雨"),
                _ => (20.0, "数据不可用"),
            };
            let temp = if unit == "fahrenheit" { c * 9.0 / 5.0 + 32.0 } else { c };
            json!({"city": city, "temperature": temp, "condition": cond})
        },
    }
}

fn calculate() -> Tool {
    Tool {
        name: "calculate",
        schema: json!({
            "name": "calculate",
            "description": "执行四则运算",
            "parameters": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["add", "sub", "mul", "div"]},
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["op", "a", "b"]
            }
        }),
        call: |args| {
            let op = args["op"].as_str().unwrap_or("");
            let a = args["a"].as_f64().unwrap_or(0.0);
            let b = args["b"].as_f64().unwrap_or(0.0);
            match op {
                "add" => json!({"result": a + b}),
                "sub" => json!({"result": a - b}),
                "mul" => json!({"result": a * b}),
                "div" if b == 0.0 => json!({"error": "division by zero"}),
                "div" => json!({"result": a / b}),
                _ => json!({"error": format!("unknown op: {op}")}),
            }
        },
    }
}

// 让 LLM 自己拆"价格 500 以上" -> min_price=500，不要在 Rust 里重做 NLP。
fn search_products() -> Tool {
    Tool {
        name: "search_products",
        schema: json!({
            "name": "search_products",
            "description": "搜索产品。可按关键词和价格区间过滤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "关键词，留空匹配全部"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"}
                }
            }
        }),
        call: |args| {
            let products = [
                (1, "笔记本电脑", 5999),
                (2, "机械键盘", 599),
                (3, "无线鼠标", 199),
            ];
            let query = args["query"].as_str().unwrap_or("");
            let min_p = args["min_price"].as_f64().unwrap_or(0.0);
            let max_p = args["max_price"].as_f64().unwrap_or(f64::INFINITY);
            let hits: Vec<_> = products
                .iter()
                .filter(|(_, name, price)| {
                    (query.is_empty() || name.contains(query))
                        && *price as f64 >= min_p
                        && *price as f64 <= max_p
                })
                .map(|(id, name, price)| json!({"id": id, "name": name, "price": price}))
                .collect();
            json!({"count": hits.len(), "results": hits})
        },
    }
}
