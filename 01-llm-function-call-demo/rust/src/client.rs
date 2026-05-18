//! client.rs —— Function Call 的两轮交互。整文件 cp 进项目即可。
//!
//! 第一轮：把 user message + tools 发给 LLM，LLM 返回 tool_calls 决策。
//! 应用层：照决策执行工具，把结果作为 role=tool 消息回灌。
//! 第二轮：LLM 看着工具结果生成最终自然语言回答。

use serde_json::{json, Value};

use crate::tools;

pub struct Config {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

/// 一次 function-call 往返，返回 LLM 的最终回答。
pub fn run(cfg: &Config, user_msg: &str) -> Result<String, String> {
    let mut messages: Vec<Value> = vec![json!({"role": "user", "content": user_msg})];

    let first = post(cfg, &json!({
        "model": cfg.model,
        "messages": messages,
        "tools": tools::schemas(),
    }))?;
    let msg = first["choices"][0]["message"].clone();

    // 没要调工具 -> 直接返回 content
    let tool_calls = msg["tool_calls"].as_array().cloned().unwrap_or_default();
    if tool_calls.is_empty() {
        return Ok(msg["content"].as_str().unwrap_or("").to_string());
    }

    // assistant 的 tool_calls 决策必须回灌，否则第二轮 LLM 看不到自己刚才说了啥
    messages.push(msg);

    // LLM 一次可能调多个工具，全跑完再回 LLM
    for tc in &tool_calls {
        let name = tc["function"]["name"].as_str().unwrap_or("");
        let args = tc["function"]["arguments"].as_str().unwrap_or("{}");
        let result = tools::call(name, args);
        messages.push(json!({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result,
        }));
    }

    let second = post(cfg, &json!({"model": cfg.model, "messages": messages}))?;
    Ok(second["choices"][0]["message"]["content"]
        .as_str()
        .unwrap_or("")
        .to_string())
}

fn post(cfg: &Config, body: &Value) -> Result<Value, String> {
    ureq::post(&format!("{}/chat/completions", cfg.base_url))
        .set("Authorization", &format!("Bearer {}", cfg.api_key))
        .set("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(60))
        .send_json(body)
        .map_err(|e| e.to_string())?
        .into_json::<Value>()
        .map_err(|e| e.to_string())
}
