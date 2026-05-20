//! main.rs —— demo 入口。
//! 默认跑三个 demo 场景；`cargo run -- verify` 验证 LLM 在三类问题上调对了工具。

mod client;
mod tools;

use client::{run, Config};
use serde_json::{json, Value};
use std::env;

fn main() {
    dotenv::from_filename("../.env").ok();
    let cfg = Config {
        base_url: env::var("API_BASE_URL").expect("API_BASE_URL not set"),
        api_key: env::var("API_KEY").unwrap_or_else(|_| "not-needed".into()),
        model: env::var("MODEL_ID").expect("MODEL_ID not set"),
    };

    let args: Vec<String> = env::args().collect();
    if args.get(1).map(String::as_str) == Some("verify") {
        verify(&cfg);
    } else {
        demo(&cfg);
    }
}

fn demo(cfg: &Config) {
    for q in [
        "北京今天天气怎么样？",
        "156 除以 12 等于多少？",
        "搜索价格在 500 元以上的产品",
    ] {
        println!(">>> {q}");
        match run(cfg, q) {
            Ok(ans) => println!("{ans}\n"),
            Err(e) => println!("  ERROR: {e}\n"),
        }
    }
}

fn verify(cfg: &Config) {
    let cases = [
        ("北京天气怎么样？", "get_weather"),
        ("156 除以 12", "calculate"),
        ("搜索笔记本相关的产品", "search_products"),
    ];
    let mut passed = 0;
    for (q, expected) in cases {
        let resp: Result<Value, String> = ureq::post(&format!("{}/chat/completions", cfg.base_url))
            .set("Authorization", &format!("Bearer {}", cfg.api_key))
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(60))
            .send_json(json!({
                "model": cfg.model,
                "messages": [{"role": "user", "content": q}],
                "tools": tools::schemas(),
            }))
            .map_err(|e| e.to_string())
            .and_then(|r| r.into_json::<Value>().map_err(|e| e.to_string()));

        let got = match &resp {
            Err(e) => format!("ERROR: {e}"),
            Ok(r) => r["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
                .as_str()
                .unwrap_or("(no tool call)")
                .to_string(),
        };
        let ok = got == expected;
        if ok {
            passed += 1;
        }
        println!("{} {q:30} expected={expected:18} got={got}", if ok { "✓" } else { "✗" });
    }
    println!("\n{}/{} passed", passed, cases.len());
}
