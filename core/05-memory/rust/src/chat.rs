//! chat.rs —— Memory + ureq 客户端 = 一个会话。整文件 cp 进项目即可。

use serde_json::{json, Value};

use crate::memory::{Memory, SummarizeFn};

pub struct Config {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

pub fn ask<M: Memory>(cfg: &Config, mem: &mut M, user_msg: &str) -> Result<String, String> {
    mem.append("user", user_msg);
    let resp: Value = ureq::post(&format!("{}/chat/completions", cfg.base_url))
        .set("Authorization", &format!("Bearer {}", cfg.api_key))
        .set("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(60))
        .send_json(json!({
            "model": cfg.model,
            "messages": mem.messages(),
            "max_tokens": 200,
            "temperature": 0.3,
        }))
        .map_err(|e| e.to_string())?
        .into_json::<Value>()
        .map_err(|e| e.to_string())?;

    let answer = resp["choices"][0]["message"]["content"].as_str().unwrap_or("").to_string();
    mem.append("assistant", &answer);
    Ok(answer)
}

/// 给 Summary 用的 summarize 函数工厂。Box 一层 dyn Fn 让 trait obj 能存。
pub fn make_summarizer(cfg: Config) -> SummarizeFn {
    Box::new(move |msgs: &[Value]| -> String {
        let mut joined = String::new();
        for m in msgs {
            joined.push_str(&format!("{}: {}\n",
                m["role"].as_str().unwrap_or(""),
                m["content"].as_str().unwrap_or("")));
        }
        let resp = ureq::post(&format!("{}/chat/completions", cfg.base_url))
            .set("Authorization", &format!("Bearer {}", cfg.api_key))
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(60))
            .send_json(json!({
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": "提取对话中的关键事实，按 - 列表，每条一行。"},
                    {"role": "user", "content": joined},
                ],
                "max_tokens": 150,
                "temperature": 0.0,
            }));
        let parsed: Result<Value, String> = resp
            .map_err(|e| e.to_string())
            .and_then(|r| r.into_json::<Value>().map_err(|e| e.to_string()));
        match parsed {
            Ok(v) => v["choices"][0]["message"]["content"].as_str().unwrap_or("").to_string(),
            Err(e) => format!("(summarize failed: {e})"),
        }
    })
}
