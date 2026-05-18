//! memory.rs —— 四种对话记忆策略。整文件 cp 进项目即可。
//!
//! Full / Window / Tokens / Summary 都实现 `Memory` trait：
//! `append(role, content)` 和 `messages() -> Vec<Value>`（OpenAI 兼容格式）。

use serde_json::{json, Value};

/// 糙估 tokens：中文 1.5 字符/t，其它 4 字符/t。生产换 tiktoken-rs。
pub fn estimate_tokens(s: &str) -> usize {
    let cn = s.chars().filter(|c| ('\u{4e00}'..='\u{9fff}').contains(c)).count();
    let other = s.chars().count() - cn;
    cn * 2 / 3 + other / 4
}

pub trait Memory {
    fn append(&mut self, role: &str, content: &str);
    fn messages(&self) -> Vec<Value>;
}

fn sys(s: &str) -> Value {
    json!({"role": "system", "content": s})
}

// ---- Full ----

pub struct Full { system: String, msgs: Vec<Value> }

impl Full {
    pub fn new(system: &str) -> Self { Self { system: system.into(), msgs: vec![] } }
}

impl Memory for Full {
    fn append(&mut self, role: &str, content: &str) {
        self.msgs.push(json!({"role": role, "content": content}));
    }
    fn messages(&self) -> Vec<Value> {
        let mut out = vec![sys(&self.system)];
        out.extend(self.msgs.clone());
        out
    }
}

// ---- Window ----

pub struct Window { system: String, msgs: Vec<Value>, k: usize }

impl Window {
    pub fn new(system: &str, k: usize) -> Self { Self { system: system.into(), msgs: vec![], k } }
}

impl Memory for Window {
    fn append(&mut self, role: &str, content: &str) {
        self.msgs.push(json!({"role": role, "content": content}));
        if self.msgs.len() > self.k {
            let drop = self.msgs.len() - self.k;
            self.msgs.drain(0..drop);
        }
    }
    fn messages(&self) -> Vec<Value> {
        let mut out = vec![sys(&self.system)];
        out.extend(self.msgs.clone());
        out
    }
}

// ---- Tokens ----

pub struct Tokens { system: String, msgs: Vec<Value>, max: usize }

impl Tokens {
    pub fn new(system: &str, max_tokens: usize) -> Self {
        Self { system: system.into(), msgs: vec![], max: max_tokens }
    }
    fn total(&self) -> usize {
        let mut t = estimate_tokens(&self.system);
        for m in &self.msgs {
            t += estimate_tokens(m["content"].as_str().unwrap_or(""));
        }
        t
    }
}

impl Memory for Tokens {
    fn append(&mut self, role: &str, content: &str) {
        self.msgs.push(json!({"role": role, "content": content}));
        // 至少留 1 条
        while self.msgs.len() > 1 && self.total() > self.max {
            self.msgs.remove(0);
        }
    }
    fn messages(&self) -> Vec<Value> {
        let mut out = vec![sys(&self.system)];
        out.extend(self.msgs.clone());
        out
    }
}

// ---- Summary ----

pub type SummarizeFn = Box<dyn Fn(&[Value]) -> String + Send>;

pub struct Summary {
    system: String,
    msgs: Vec<Value>,
    k: usize,
    summarize: SummarizeFn,
    summary: String,
}

impl Summary {
    pub fn new(system: &str, k: usize, summarize: SummarizeFn) -> Self {
        Self { system: system.into(), msgs: vec![], k, summarize, summary: String::new() }
    }
}

impl Memory for Summary {
    fn append(&mut self, role: &str, content: &str) {
        self.msgs.push(json!({"role": role, "content": content}));
        if self.msgs.len() < self.k {
            return;
        }
        let new_sum = (self.summarize)(&self.msgs);
        if self.summary.is_empty() {
            self.summary = new_sum;
        } else {
            // 累积叠加，旧事实不能丢
            self.summary.push('\n');
            self.summary.push_str(&new_sum);
        }
        self.msgs.clear();
    }
    fn messages(&self) -> Vec<Value> {
        let mut out = vec![sys(&self.system)];
        if !self.summary.is_empty() {
            out.push(sys(&format!("历史事实：{}", self.summary)));
        }
        out.extend(self.msgs.clone());
        out
    }
}
