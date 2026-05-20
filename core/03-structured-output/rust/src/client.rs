//! client.rs —— 结构化输出。整文件 cp 进项目即可。
//!
//! `response_format.json_schema.strict=true` 让 OpenAI 在解码时按 schema 约束，
//! content 一定是合法 JSON 且字段类型/枚举严格匹配。

use serde_json::{json, Value};

pub struct Config {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

/// 让 LLM 按 schema 返回 JSON，直接 parse 成 Value。
/// 失败：网络/HTTP/JSON 解析错都包装成 String。
pub fn extract(cfg: &Config, system: &str, user: &str, name: &str, schema: &Value) -> Result<Value, String> {
    let resp: Value = ureq::post(&format!("{}/chat/completions", cfg.base_url))
        .set("Authorization", &format!("Bearer {}", cfg.api_key))
        .set("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(60))
        .send_json(json!({
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "schema": schema,
                    "strict": true,
                },
            },
        }))
        .map_err(|e| e.to_string())?
        .into_json::<Value>()
        .map_err(|e| e.to_string())?;

    let content = resp["choices"][0]["message"]["content"]
        .as_str()
        .ok_or_else(|| format!("no content in response: {resp}"))?;
    // strict 模式下 content 必是合法 JSON；parse 失败说明 schema 自己有问题
    // 或本地模型没真支持 strict
    serde_json::from_str(content).map_err(|e| format!("json parse: {e}; raw: {content}"))
}
