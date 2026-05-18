//! orchestrator.rs —— 多 agent 编排。整文件 cp 进项目即可。
//!
//! 并行用 std::thread —— 不引入 tokio。ureq 是同步阻塞，thread 跑就行。

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::thread;

use crate::agent::Agent;

pub struct Step {
    pub id: String,
    pub agent: String,
    pub task: String,
    pub depends_on: Vec<String>,
}

const MAX_CTX_CHARS: usize = 400;

fn build_context(results: &HashMap<String, String>, deps: &[String]) -> String {
    let mut parts = Vec::new();
    for d in deps {
        if let Some(v) = results.get(d) {
            let truncated = if v.chars().count() > MAX_CTX_CHARS {
                let mut s: String = v.chars().take(MAX_CTX_CHARS).collect();
                s.push_str("...(已截断)");
                s
            } else {
                v.clone()
            };
            parts.push(format!("[{d}]\n{truncated}"));
        }
    }
    parts.join("\n\n")
}

pub fn run_sequential(agents: &HashMap<String, Agent>, workflow: &[Step]) -> Result<HashMap<String, String>, String> {
    let mut results: HashMap<String, String> = HashMap::new();
    for s in workflow {
        let agent = agents.get(&s.agent).ok_or_else(|| format!("no agent: {}", s.agent))?;
        let ctx = build_context(&results, &s.depends_on);
        let out = agent.execute(&s.task, &ctx)?;
        results.insert(s.id.clone(), out);
    }
    Ok(results)
}

/// 并行：每个 step 起一个 thread。Agent 必须能跨线程发送，下面用 Arc 共享。
pub fn run_parallel(agents: Arc<HashMap<String, Agent>>, steps: Vec<Step>) -> HashMap<String, String> {
    let results: Arc<Mutex<HashMap<String, String>>> = Arc::new(Mutex::new(HashMap::new()));
    let mut handles = Vec::new();
    for s in steps {
        let agents = Arc::clone(&agents);
        let results = Arc::clone(&results);
        handles.push(thread::spawn(move || {
            let out = match agents.get(&s.agent) {
                Some(a) => a.execute(&s.task, "").unwrap_or_else(|e| format!("ERROR: {e}")),
                None => format!("ERROR: no agent {}", s.agent),
            };
            results.lock().unwrap().insert(s.id, out);
        }));
    }
    for h in handles {
        let _ = h.join();
    }
    Arc::try_unwrap(results).unwrap().into_inner().unwrap()
}
