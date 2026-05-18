//! main.rs —— demo only：三个场景（简历 / 产品 / 情感分类）。

mod client;
mod schemas;

use client::{extract, Config};
use std::env;

fn main() {
    dotenv::from_filename("../.env").ok();
    let cfg = Config {
        base_url: env::var("API_BASE_URL").expect("API_BASE_URL not set"),
        api_key: env::var("API_KEY").unwrap_or_else(|_| "not-needed".into()),
        model: env::var("MODEL_ID").expect("MODEL_ID not set"),
    };

    run(&cfg, "简历提取",
        "提取简历信息。",
        "张三，28岁，Python 工程师，邮箱 zs@example.com，擅长 Django、FastAPI、PostgreSQL。",
        "resume", &schemas::resume());

    run(&cfg, "产品信息提取",
        "提取产品信息。",
        "iPhone 15 Pro 国行 9999 元，苹果出品，目前有货。",
        "product", &schemas::product());

    run(&cfg, "情感分类（label 限定 positive/neutral/negative）",
        "对文本做情感分类，给出 label / confidence(0-1) / 一句话 reason。",
        "这部电影完全是浪费时间，特效粗糙，剧情拖沓。",
        "sentiment", &schemas::sentiment());
}

fn run(cfg: &Config, label: &str, system: &str, user: &str, name: &str, schema: &serde_json::Value) {
    match extract(cfg, system, user, name, schema) {
        Ok(v) => println!("\n>>> {label}\n{}", serde_json::to_string_pretty(&v).unwrap()),
        Err(e) => println!("\n>>> {label}\n  ERROR: {e}"),
    }
}
