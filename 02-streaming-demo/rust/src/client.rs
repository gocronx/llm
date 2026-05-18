//! client.rs —— 流式输出。整文件 cp 进项目即可。
//!
//! ureq 是同步 HTTP，本身不解 SSE。我们自己拆 `data: <json>\n\n` 帧，遇到
//! `[DONE]` 就停。stream_text 把每个 content delta 给到 on_delta；
//! stream_with_tools 在第一轮里按 index 累积 tool_calls，执行后第二轮再流。
//!
//! 关键点：arguments 永远是 JSON 字符串，必须用字符串拼接而不是 dict.update
//! —— 半截 JSON 不是合法对象。

use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::io::{BufRead, BufReader, Read};

use crate::tools;

pub struct Config {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

pub enum Event {
    Text(String),
    Tool { name: String, args: String, result: String },
}

/// 纯文本流式：把每个 delta content 推给 on_delta。
pub fn stream_text(cfg: &Config, user_msg: &str, mut on_delta: impl FnMut(&str)) -> Result<(), String> {
    let body = json!({
        "model": cfg.model,
        "messages": [{"role": "user", "content": user_msg}],
        "stream": true,
    });
    each_sse(cfg, &body, |chunk| {
        if let Some(s) = chunk["choices"][0]["delta"]["content"].as_str() {
            on_delta(s);
        }
    })
}

/// 流式 + function call。Event 通过 on_event 回调送给调用方。
pub fn stream_with_tools(cfg: &Config, user_msg: &str, mut on_event: impl FnMut(Event)) -> Result<(), String> {
    let mut messages: Vec<Value> = vec![json!({"role": "user", "content": user_msg})];

    // 第一轮：累积 tool_calls。index -> (id, name, args)
    let mut acc: BTreeMap<u64, (String, String, String)> = BTreeMap::new();
    let body = json!({
        "model": cfg.model,
        "messages": messages,
        "tools": tools::schemas(),
        "stream": true,
    });
    each_sse(cfg, &body, |chunk| {
        let tcs = match chunk["choices"][0]["delta"]["tool_calls"].as_array() {
            Some(v) => v,
            None => return,
        };
        for tc in tcs {
            let idx = tc["index"].as_u64().unwrap_or(0);
            let entry = acc.entry(idx).or_insert_with(|| (String::new(), String::new(), String::new()));
            if let Some(id) = tc["id"].as_str() {
                entry.0 = id.to_string();
            }
            if let Some(name) = tc["function"]["name"].as_str() {
                entry.1 = name.to_string();
            }
            if let Some(args) = tc["function"]["arguments"].as_str() {
                entry.2.push_str(args);
            }
        }
    })?;

    if acc.is_empty() {
        // 没要工具：重发一次纯文本流（也可以缓存第一轮的 content delta，但代码复杂度不划算）
        return stream_text(cfg, user_msg, |s| on_event(Event::Text(s.to_string())));
    }

    // 回灌 assistant 的 tool_calls 决策
    let tool_calls: Vec<Value> = acc
        .values()
        .map(|(id, name, args)| json!({
            "id": id, "type": "function",
            "function": {"name": name, "arguments": args},
        }))
        .collect();
    messages.push(json!({"role": "assistant", "content": null, "tool_calls": tool_calls}));

    for (id, name, args) in acc.values() {
        let result = tools::call(name, args);
        on_event(Event::Tool {
            name: name.clone(),
            args: args.clone(),
            result: result.clone(),
        });
        messages.push(json!({"role": "tool", "tool_call_id": id, "content": result}));
    }

    // 第二轮流式
    let body = json!({"model": cfg.model, "messages": messages, "stream": true});
    each_sse(cfg, &body, |chunk| {
        if let Some(s) = chunk["choices"][0]["delta"]["content"].as_str() {
            on_event(Event::Text(s.to_string()));
        }
    })
}

/// 拆 `data: <json>\n\n` 帧，遇到 `[DONE]` 停。每帧 json 推给回调。
fn each_sse(cfg: &Config, body: &Value, mut on_chunk: impl FnMut(&Value)) -> Result<(), String> {
    let resp = ureq::post(&format!("{}/chat/completions", cfg.base_url))
        .set("Authorization", &format!("Bearer {}", cfg.api_key))
        .set("Content-Type", "application/json")
        .set("Accept", "text/event-stream")
        .timeout(std::time::Duration::from_secs(60))
        .send_json(body)
        .map_err(|e| e.to_string())?;
    let reader: Box<dyn Read + Send + Sync> = resp.into_reader();
    let reader = BufReader::new(reader);
    for line in reader.lines() {
        let line = line.map_err(|e| e.to_string())?;
        let line = line.trim_start();
        let data = match line.strip_prefix("data: ") {
            Some(d) => d,
            None => continue,
        };
        if data == "[DONE]" {
            break;
        }
        if let Ok(v) = serde_json::from_str::<Value>(data) {
            on_chunk(&v);
        }
    }
    Ok(())
}
