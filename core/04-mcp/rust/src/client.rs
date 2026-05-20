//! client.rs —— OpenAI ↔ MCP 桥接。整文件 cp 进项目即可。

use serde_json::{json, Value};

use crate::mcp::MCPClient;

pub struct Config {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

/// 拿 MCP server 的 tools，转成 OpenAI 期望的 tools schema。
pub fn openai_tools(mcp: &mut MCPClient) -> Result<Vec<Value>, String> {
    let tools = mcp.list_tools()?;
    Ok(tools.into_iter().map(|t| json!({
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.input_schema,
        }
    })).collect())
}

/// 多轮 LLM ↔ MCP-tools 循环，直到 LLM 不再 call tool。
pub fn chat(cfg: &Config, mcp: &mut MCPClient, user_msg: &str, max_rounds: usize) -> Result<String, String> {
    let tools = openai_tools(mcp)?;
    let mut messages: Vec<Value> = vec![json!({"role": "user", "content": user_msg})];

    for _ in 0..max_rounds {
        let resp: Value = ureq::post(&format!("{}/chat/completions", cfg.base_url))
            .set("Authorization", &format!("Bearer {}", cfg.api_key))
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(60))
            .send_json(json!({
                "model": cfg.model,
                "messages": messages,
                "tools": tools,
            }))
            .map_err(|e| e.to_string())?
            .into_json::<Value>()
            .map_err(|e| e.to_string())?;

        let msg = resp["choices"][0]["message"].clone();
        let tcs = msg["tool_calls"].as_array().cloned().unwrap_or_default();
        if tcs.is_empty() {
            return Ok(msg["content"].as_str().unwrap_or("").to_string());
        }

        // 回灌 assistant 的 tool_calls 决策
        messages.push(msg.clone());
        for tc in &tcs {
            let name = tc["function"]["name"].as_str().unwrap_or("");
            let args_str = tc["function"]["arguments"].as_str().unwrap_or("{}");
            let args: Value = serde_json::from_str(args_str).unwrap_or(json!({}));
            let result = mcp.call_tool(name, args).unwrap_or_else(|e| format!("{{\"error\": \"{e}\"}}"));
            messages.push(json!({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            }));
        }
    }
    Ok("(max rounds reached)".into())
}
