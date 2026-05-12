mod functions;

use dotenv::dotenv;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::env;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Message {
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<ToolCall>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_call_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct ToolCall {
    id: String,
    #[serde(rename = "type")]
    tool_type: String,
    function: FunctionCall,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct FunctionCall {
    name: String,
    arguments: String,
}

#[derive(Debug, Serialize)]
struct Tool {
    #[serde(rename = "type")]
    tool_type: String,
    function: functions::FunctionDefinition,
}

#[derive(Debug, Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<Tool>>,
    max_tokens: i32,
}

#[derive(Debug, Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: Message,
}

fn call_llm(
    messages: Vec<Message>,
    functions: Option<Vec<functions::FunctionDefinition>>,
) -> Result<ChatResponse, Box<dyn std::error::Error>> {
    dotenv().ok();
    let api_base_url = env::var("API_BASE_URL")?;
    let api_key = env::var("API_KEY")?;
    let model_id = env::var("MODEL_ID")?;

    let tools = functions.map(|funcs| {
        funcs
            .into_iter()
            .map(|f| Tool {
                tool_type: "function".to_string(),
                function: f,
            })
            .collect()
    });

    let request = ChatRequest {
        model: model_id,
        messages,
        tools,
        max_tokens: 1000,
    };

    let response = ureq::post(&format!("{}/chat/completions", api_base_url))
        .set("Authorization", &format!("Bearer {}", api_key))
        .set("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(60))
        .send_json(&request)?;

    let chat_response: ChatResponse = response.into_json()?;
    Ok(chat_response)
}

fn run_function_call(user_message: &str) {
    println!("{}", "=".repeat(60));
    println!("用户: {}", user_message);
    println!("{}\n", "=".repeat(60));

    let mut messages = vec![Message {
        role: "user".to_string(),
        content: Some(user_message.to_string()),
        tool_calls: None,
        tool_call_id: None,
        name: None,
    }];

    // 第一次调用：让 LLM 决定是否调用函数
    println!("→ 发送请求到 LLM...");
    let response = match call_llm(messages.clone(), Some(functions::get_function_definitions())) {
        Ok(r) => r,
        Err(e) => {
            println!("✗ API 调用失败: {}\n", e);
            return;
        }
    };

    let message = &response.choices[0].message;

    if let Some(tool_calls) = &message.tool_calls {
        if !tool_calls.is_empty() {
            // LLM 决定调用函数
            let tool_call = &tool_calls[0];
            let func_name = &tool_call.function.name;
            let func_args: Value = serde_json::from_str(&tool_call.function.arguments).unwrap();

            println!("✓ LLM 调用函数: {}", func_name);
            println!("  参数: {}\n", func_args);

            // 执行函数
            println!("→ 执行函数...");
            let result = functions::execute_function(func_name, &func_args);
            println!("✓ 函数返回: {}\n", result);

            // 第二次调用：生成最终回答
            messages.push(Message {
                role: message.role.clone(),
                content: message.content.clone(),
                tool_calls: message.tool_calls.clone(),
                tool_call_id: None,
                name: None,
            });
            messages.push(Message {
                role: "tool".to_string(),
                content: Some(result),
                tool_calls: None,
                tool_call_id: Some(tool_call.id.clone()),
                name: Some(func_name.clone()),
            });

            println!("→ 生成最终回答...");
            match call_llm(messages, None) {
                Ok(final_response) => {
                    if let Some(answer) = &final_response.choices[0].message.content {
                        println!("✓ 最终回答:\n{}\n", answer);
                    }
                }
                Err(e) => {
                    println!("✗ API 调用失败: {}\n", e);
                }
            }
        }
    } else {
        // 直接回答
        if let Some(content) = &message.content {
            println!("✓ LLM 直接回答:\n{}\n", content);
        }
    }
}

fn main() {
    // 从上级目录加载 .env
    dotenv::from_filename("../.env").ok();

    println!("\n{}", "=".repeat(60));
    println!("Function Call Demo (Rust)");
    println!("{}", "=".repeat(60));

    run_function_call("北京今天天气怎么样？");
    run_function_call("156 除以 12 等于多少？");
    run_function_call("搜索价格在500元以上的产品");
}
