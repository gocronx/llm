//! main.rs —— demo only：writer → reviewer → editor 顺序；3 写手并行。

mod agent;
mod orchestrator;

use agent::{Agent, Config};
use orchestrator::{run_parallel, run_sequential, Step};
use std::collections::HashMap;
use std::env;
use std::sync::Arc;

fn main() {
    dotenv::from_filename("../.env").ok();
    let cfg = Config {
        base_url: env::var("API_BASE_URL").expect("API_BASE_URL not set"),
        api_key: env::var("API_KEY").unwrap_or_else(|_| "not-needed".into()),
        model: env::var("MODEL_ID").expect("MODEL_ID not set"),
    };

    let agents: HashMap<String, Agent> = [
        ("writer", "你是技术博客写手。给出 200 字内的文章主体，不要标题。"),
        ("reviewer", "你是技术评审员。读上游产物，按 - 列表给 3 条具体改进建议，每条不超过 20 字。"),
        ("editor", "你是编辑。综合 writer 的初稿和 reviewer 的建议，输出最终成稿。禁止添加解释。"),
    ].into_iter().map(|(n, r)| {
        (n.to_string(), Agent {
            name: n.to_string(),
            role: r.to_string(),
            cfg: cfg.clone(),
            temperature: 0.3,
        })
    }).collect();

    // ---- 顺序 ----
    println!("\n=== 顺序工作流：writer → reviewer → editor ===");
    let wf = vec![
        Step { id: "draft".into(),  agent: "writer".into(),
               task: "写一段关于 Rust 内存安全的简短科普".into(), depends_on: vec![] },
        Step { id: "review".into(), agent: "reviewer".into(),
               task: "评审上面的初稿".into(), depends_on: vec!["draft".into()] },
        Step { id: "final".into(),  agent: "editor".into(),
               task: "按 reviewer 建议修改 draft，输出终稿".into(),
               depends_on: vec!["draft".into(), "review".into()] },
    ];
    let results = run_sequential(&agents, &wf).unwrap_or_else(|e| {
        eprintln!("error: {e}");
        HashMap::new()
    });
    for id in ["draft", "review", "final"] {
        if let Some(v) = results.get(id) {
            println!("\n--- {id} ---\n{v}");
        }
    }

    // ---- 并行 ----
    println!("\n=== 并行工作流：3 个 writer 各写一段 ===");
    let steps = vec![
        Step { id: "py".into(),   agent: "writer".into(), task: "写一句 Python 的优点".into(), depends_on: vec![] },
        Step { id: "rust".into(), agent: "writer".into(), task: "写一句 Rust 的优点".into(),   depends_on: vec![] },
        Step { id: "go".into(),   agent: "writer".into(), task: "写一句 Go 的优点".into(),     depends_on: vec![] },
    ];
    let r = run_parallel(Arc::new(agents), steps);
    for id in ["py", "rust", "go"] {
        if let Some(v) = r.get(id) {
            println!("  [{id}] {}", v.trim());
        }
    }
}
