//! agent.rs —— 单 Agent。整文件 cp 进项目即可。

use serde_json::{json, Value};

#[derive(Clone)]
pub struct Config {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

pub struct Agent {
    pub name: String,
    pub role: String,
    pub cfg: Config,
    pub temperature: f32, // 默认 0.3
}

impl Agent {
    pub fn execute(&self, task: &str, extra: &str) -> Result<String, String> {
        let user = if extra.is_empty() {
            task.to_string()
        } else {
            format!("{task}\n\n上游产物：\n{extra}")
        };
        let temp = if self.temperature == 0.0 { 0.3 } else { self.temperature };
        let resp: Value = ureq::post(&format!("{}/chat/completions", self.cfg.base_url))
            .set("Authorization", &format!("Bearer {}", self.cfg.api_key))
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(60))
            .send_json(json!({
                "model": self.cfg.model,
                "messages": [
                    {"role": "system", "content": self.role},
                    {"role": "user", "content": user},
                ],
                "temperature": temp,
                "max_tokens": 400,
            }))
            .map_err(|e| e.to_string())?
            .into_json::<Value>()
            .map_err(|e| e.to_string())?;
        Ok(resp["choices"][0]["message"]["content"].as_str().unwrap_or("").to_string())
    }
}
