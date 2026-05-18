//! tools.rs —— 工具注册表。只放一个 get_weather，演示流式 + 工具的 delta 累积。

use serde_json::{json, Value};

pub struct Tool {
    pub name: &'static str,
    pub schema: Value,
    pub call: fn(Value) -> Value,
}

pub fn all() -> Vec<Tool> {
    vec![weather()]
}

pub fn schemas() -> Vec<Value> {
    all()
        .into_iter()
        .map(|t| json!({"type": "function", "function": t.schema}))
        .collect()
}

pub fn call(name: &str, args_json: &str) -> String {
    for t in all() {
        if t.name == name {
            let args: Value = serde_json::from_str(args_json).unwrap_or(json!({}));
            return (t.call)(args).to_string();
        }
    }
    json!({"error": format!("unknown tool: {name}")}).to_string()
}

fn weather() -> Tool {
    Tool {
        name: "get_weather",
        schema: json!({
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"]
            }
        }),
        call: |args| {
            let city = args["city"].as_str().unwrap_or("");
            let (t, cond) = match city {
                "北京" => (15, "晴"),
                "上海" => (20, "多云"),
                "深圳" => (25, "小雨"),
                _ => (18, "数据不可用"),
            };
            json!({"city": city, "temperature": t, "condition": cond})
        },
    }
}
