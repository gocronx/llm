//! main.rs —— demo only：同一组对话喂给四种 memory。

mod chat;
mod memory;

use chat::{ask, make_summarizer, Config};
use memory::{estimate_tokens, Full, Memory, Summary, Tokens, Window};
use std::env;

const SYSTEM: &str = "你是友好的助手，用一句话简短回答。";

const DIALOG: [&str; 6] = [
    "你好，我叫张三",
    "我今年 25 岁",
    "我喜欢编程",
    "我刚才说我叫什么？",
    "我多大？",
    "我有什么爱好？",
];

fn cfg() -> Config {
    Config {
        base_url: env::var("API_BASE_URL").expect("API_BASE_URL not set"),
        api_key: env::var("API_KEY").unwrap_or_else(|_| "not-needed".into()),
        model: env::var("MODEL_ID").expect("MODEL_ID not set"),
    }
}

fn run<M: Memory>(label: &str, mem: &mut M) {
    println!("\n=== {label} ===");
    let c = cfg();
    for q in DIALOG {
        match ask(&c, mem, q) {
            Ok(ans) => {
                let toks: usize = mem.messages().iter()
                    .map(|m| estimate_tokens(m["content"].as_str().unwrap_or("")))
                    .sum();
                let n = mem.messages().len();
                let short: String = ans.chars().take(100).collect();
                println!("  Q: {q}\n  A: {short}  [ctx≈{toks}t, {n}msg]");
            }
            Err(e) => println!("  ERROR: {e}"),
        }
    }
}

fn main() {
    dotenv::from_filename("../.env").ok();
    run("Full（全留）", &mut Full::new(SYSTEM));
    run("Window(k=4)", &mut Window::new(SYSTEM, 4));
    run("Tokens(max=200)", &mut Tokens::new(SYSTEM, 200));
    run("Summary(k=4)", &mut Summary::new(SYSTEM, 4, make_summarizer(cfg())));
}
