//! main.rs —— demo only：两个场景。

mod client;
mod tools;

use client::{stream_text, stream_with_tools, Config, Event};
use std::env;
use std::io::Write;
use std::time::Instant;

fn main() {
    dotenv::from_filename("../.env").ok();
    let cfg = Config {
        base_url: env::var("API_BASE_URL").expect("API_BASE_URL not set"),
        api_key: env::var("API_KEY").unwrap_or_else(|_| "not-needed".into()),
        model: env::var("MODEL_ID").expect("MODEL_ID not set"),
    };

    scenario_text(&cfg);
    println!();
    scenario_tools(&cfg);
}

fn scenario_text(cfg: &Config) {
    println!(">>> 纯文本流式：写一段 50 字内的 AI 简介");
    let t0 = Instant::now();
    let mut first_at: Option<f64> = None;
    let mut n = 0u32;
    let r = stream_text(cfg, "用 50 字内介绍人工智能。", |s| {
        if first_at.is_none() {
            first_at = Some(t0.elapsed().as_secs_f64());
        }
        print!("{s}");
        std::io::stdout().flush().ok();
        n += 1;
    });
    if let Err(e) = r {
        println!("\nERROR: {e}");
        return;
    }
    println!(
        "\n[首字 {:.2}s / 总 {:.2}s / {n} chunks]",
        first_at.unwrap_or(0.0),
        t0.elapsed().as_secs_f64()
    );
}

fn scenario_tools(cfg: &Config) {
    println!(">>> 流式 + function call：北京天气");
    let r = stream_with_tools(cfg, "北京今天天气怎么样？", |ev| match ev {
        Event::Tool { name, args, result } => {
            println!("[tool] {name}({args}) -> {result}");
        }
        Event::Text(s) => {
            print!("{s}");
            std::io::stdout().flush().ok();
        }
    });
    if let Err(e) = r {
        println!("\nERROR: {e}");
    }
    println!();
}
