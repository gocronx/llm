use colored::*;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;
use std::env;
use std::fs;

#[derive(Serialize, Deserialize, Clone)]
struct Message {
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<ToolCall>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_call_id: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
struct ToolCall {
    id: String,
    #[serde(rename = "type")]
    tool_type: String,
    function: FunctionCall,
}

#[derive(Serialize, Deserialize, Clone)]
struct FunctionCall {
    name: String,
    arguments: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    tools: Vec<serde_json::Value>,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: Message,
}

struct MCPClient {
    api_url: String,
    api_key: String,
    model: String,
    base_path: String,
}

impl MCPClient {
    fn new(api_url: String, api_key: String, model: String, base_path: String) -> Self {
        fs::create_dir_all(&base_path).ok();
        MCPClient {
            api_url,
            api_key,
            model,
            base_path,
        }
    }

    fn get_tools(&self) -> Vec<serde_json::Value> {
        vec![
            json!({
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径"
                            }
                        },
                        "required": ["path"]
                    }
                }
            }),
            json!({
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "写入文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径"
                            },
                            "content": {
                                "type": "string",
                                "description": "文件内容"
                            }
                        },
                        "required": ["path", "content"]
                    }
                }
            }),
            json!({
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "列出目录内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "目录路径",
                                "default": "."
                            }
                        }
                    }
                }
            }),
        ]
    }

    fn call_tool(&self, name: &str, arguments: &HashMap<String, serde_json::Value>) -> String {
        match name {
            "read_file" => {
                let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
                self.read_file(path)
            }
            "write_file" => {
                let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
                let content = arguments
                    .get("content")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                self.write_file(path, content)
            }
            "list_directory" => {
                let path = arguments
                    .get("path")
                    .and_then(|v| v.as_str())
                    .unwrap_or(".");
                self.list_directory(path)
            }
            _ => format!("未知工具: {}", name),
        }
    }

    fn read_file(&self, path: &str) -> String {
        let full_path = format!("{}/{}", self.base_path, path);
        match fs::read_to_string(&full_path) {
            Ok(content) => content,
            Err(e) => format!("读取失败: {}", e),
        }
    }

    fn write_file(&self, path: &str, content: &str) -> String {
        let full_path = format!("{}/{}", self.base_path, path);
        match fs::write(&full_path, content) {
            Ok(_) => format!("成功写入文件: {}", path),
            Err(e) => format!("写入失败: {}", e),
        }
    }

    fn list_directory(&self, path: &str) -> String {
        let full_path = format!("{}/{}", self.base_path, path);
        match fs::read_dir(&full_path) {
            Ok(entries) => {
                let mut result = String::new();
                for entry in entries {
                    if let Ok(entry) = entry {
                        let metadata = entry.metadata().ok();
                        if let Some(meta) = metadata {
                            if meta.is_dir() {
                                result.push_str(&format!("📁 {}/\n", entry.file_name().to_string_lossy()));
                            } else {
                                result.push_str(&format!(
                                    "📄 {} ({} bytes)\n",
                                    entry.file_name().to_string_lossy(),
                                    meta.len()
                                ));
                            }
                        }
                    }
                }
                if result.is_empty() {
                    "目录为空".to_string()
                } else {
                    result
                }
            }
            Err(e) => format!("列出目录失败: {}", e),
        }
    }

    fn chat(&self, mut messages: Vec<Message>, max_rounds: usize) -> String {
        for round in 1..=max_rounds {
            println!("\n{}--- 第 {} 轮 ---{}\n", "".cyan(), round, "".clear());

            let request = ChatRequest {
                model: self.model.clone(),
                messages: messages.clone(),
                tools: self.get_tools(),
            };

            let url = format!("{}/chat/completions", self.api_url);
            let response = ureq::post(&url)
                .set("Authorization", &format!("Bearer {}", self.api_key))
                .set("Content-Type", "application/json")
                .send_json(&request);

            match response {
                Ok(resp) => {
                    if let Ok(chat_resp) = resp.into_json::<ChatResponse>() {
                        let message = &chat_resp.choices[0].message;

                        if let Some(tool_calls) = &message.tool_calls {
                            messages.push(message.clone());

                            for tool_call in tool_calls {
                                let args: HashMap<String, serde_json::Value> =
                                    serde_json::from_str(&tool_call.function.arguments)
                                        .unwrap_or_default();

                                println!(
                                    "{}🔧 调用工具:{} {}",
                                    "".yellow(),
                                    "".clear(),
                                    tool_call.function.name
                                );
                                println!(
                                    "{}   参数:{} {}",
                                    "".yellow(),
                                    "".clear(),
                                    tool_call.function.arguments
                                );

                                let result = self.call_tool(&tool_call.function.name, &args);
                                let display_result = if result.len() > 100 {
                                    format!("{}...", &result[..100])
                                } else {
                                    result.clone()
                                };
                                println!("{}   结果:{} {}", "".yellow(), "".clear(), display_result);

                                messages.push(Message {
                                    role: "tool".to_string(),
                                    content: Some(result),
                                    tool_calls: None,
                                    tool_call_id: Some(tool_call.id.clone()),
                                });
                            }
                            continue;
                        }

                        println!("\n{}✅ 最终答案:{}\n", "".green(), "".clear());
                        return message.content.clone().unwrap_or_default();
                    }
                }
                Err(e) => return format!("API 错误: {}", e),
            }
        }

        "达到最大轮数限制".to_string()
    }
}

fn main() {
    dotenv::from_filename("../.env").ok();

    let api_url = env::var("API_BASE_URL").expect("API_BASE_URL not set");
    let api_key = env::var("API_KEY").expect("API_KEY not set");
    let model = env::var("MODEL_ID").expect("MODEL_ID not set");

    println!("{}{}", "".cyan(), "=".repeat(60));
    println!("MCP (Model Context Protocol) 演示");
    println!("{}{}\n", "=".repeat(60), "".clear());

    let client = MCPClient::new(api_url, api_key, model, "test_workspace".to_string());

    println!("{}场景:{} 让 AI 创建一个 TODO 列表文件\n", "".green(), "".clear());
    println!("{}{}{}\n", "".cyan(), "-".repeat(60), "".clear());

    let messages = vec![Message {
        role: "user".to_string(),
        content: Some(
            "请帮我创建一个 todo.txt 文件，内容包括：1. 学习 MCP 协议 2. 实现 MCP Server 3. 测试 MCP Client"
                .to_string(),
        ),
        tool_calls: None,
        tool_call_id: None,
    }];

    let result = client.chat(messages, 5);
    println!("{}", result);

    println!("\n{}{}{}\n", "".cyan(), "-".repeat(60), "".clear());

    println!("{}验证:{} 检查文件是否创建成功\n", "".green(), "".clear());

    let messages2 = vec![Message {
        role: "user".to_string(),
        content: Some("请列出当前目录的文件，然后读取 todo.txt 的内容".to_string()),
        tool_calls: None,
        tool_call_id: None,
    }];

    let result2 = client.chat(messages2, 5);
    println!("{}", result2);

    println!("\n{}{}", "".cyan(), "=".repeat(60));
    println!("MCP 的价值");
    println!("{}{}\n", "=".repeat(60), "".clear());

    println!("{}MCP vs Function Call:{}\n", "".yellow(), "".clear());
    println!("Function Call:");
    println!("  - 每个应用自己定义工具格式");
    println!("  - 没有统一标准");
    println!("  - 难以复用\n");

    println!("MCP:");
    println!("  - 统一的协议标准");
    println!("  - Server 可以被多个 Client 复用");
    println!("  - 生态系统更健康\n");

    println!("{}结论:{}", "".green(), "".clear());
    println!("  MCP 是 Function Call 的标准化演进");
    println!("  长期价值更高\n");
}
