//! schemas.rs —— 三个示例 JSON Schema。
//! OpenAI strict 模式硬规则：每个 object 都得有 additionalProperties:false；
//! required 必须列出 properties 里所有 key；不支持 default / format。

use serde_json::{json, Value};

/// 简历提取。
pub fn resume() -> Value {
    obj(
        json!({
            "name":     {"type": "string"},
            "age":      {"type": "integer"},
            "position": {"type": "string"},
            "email":    {"type": "string"},
            "skills":   {"type": "array", "items": {"type": "string"}},
        }),
        &["name", "age", "position", "email", "skills"],
    )
}

/// 产品信息（嵌套对象 + enum）。
pub fn product() -> Value {
    let price = obj(
        json!({
            "amount":   {"type": "number"},
            "currency": {"type": "string", "enum": ["CNY", "USD", "EUR"]},
        }),
        &["amount", "currency"],
    );
    obj(
        json!({
            "name":     {"type": "string"},
            "brand":    {"type": "string"},
            "price":    price,
            "in_stock": {"type": "boolean"},
        }),
        &["name", "brand", "price", "in_stock"],
    )
}

/// 情感分类（label 限定 enum）。
pub fn sentiment() -> Value {
    obj(
        json!({
            "label":      {"type": "string", "enum": ["positive", "neutral", "negative"]},
            "confidence": {"type": "number"},
            "reason":     {"type": "string"},
        }),
        &["label", "confidence", "reason"],
    )
}

// 把"每个 object 都填 additionalProperties:false"的噪音抹掉
fn obj(properties: Value, required: &[&str]) -> Value {
    json!({
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": false,
    })
}
