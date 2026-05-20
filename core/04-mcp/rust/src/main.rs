//! main.rs —— demo only：Rust 客户端拉 Python MCP server，让 LLM 操作 todo.txt。

mod client;
mod mcp;

use client::{chat, Config};
use mcp::MCPClient;
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    dotenv::from_filename("../.env").ok();
    let cfg = Config {
        base_url: env::var("API_BASE_URL").expect("API_BASE_URL not set"),
        api_key: env::var("API_KEY").unwrap_or_else(|_| "not-needed".into()),
        model: env::var("MODEL_ID").expect("MODEL_ID not set"),
    };

    let workspace = std::env::current_dir().unwrap().join("test_workspace");
    fs::create_dir_all(&workspace).unwrap();

    let py_server = PathBuf::from("../python/server.py").canonicalize().unwrap();
    let workspace_str = workspace.to_string_lossy().to_string();
    let mut mcp = MCPClient::spawn(
        "python3",
        &[py_server.to_str().unwrap(), &workspace_str],
    ).expect("spawn mcp server");

    for q in [
        "请在 todo.txt 里写三条 todo：1. 学习 MCP 2. 写 demo 3. 提 PR",
        "先列出当前目录，然后读 todo.txt 的内容回给我。",
    ] {
        println!(">>> {q}");
        match chat(&cfg, &mut mcp, q, 6) {
            Ok(ans) => println!("{ans}\n"),
            Err(e) => println!("  ERROR: {e}\n"),
        }
    }
}
