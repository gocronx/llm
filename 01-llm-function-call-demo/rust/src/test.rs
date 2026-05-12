mod functions;

use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Message {
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<ToolCall>>,
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
    tools: Vec<Tool>,
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

fn test_function_call() {
    dotenv::from_filename("../.env").ok();
    let api_base_url = env::var("API_BASE_URL").expect("API_BASE_URL not found");
    let api_key = env::var("API_KEY").expect("API_KEY not found");
    let model_id = env::var("MODEL_ID").expect("MODEL_ID not found");

    println!("\n{}", "=".repeat(60));
    println!("Function Call 测试 (Rust)");
    println!("{}\n", "=".repeat(60));

    let test_cases = vec![
        ("天气查询", "北京天气怎么样？", "get_weather"),
        ("数学计算", "156 除以 12", "calculate"),
        (
            "数据库搜索",
            "帮我在数据库中搜索笔记本相关的产品",
            "search_database",
        ),
    ];

    let mut results = Vec::new();

    for (name, question, expected) in test_cases {
        println!("测试: {}", name);
        println!("问题: {}", question);

        let tools: Vec<Tool> = functions::get_function_definitions()
            .into_iter()
            .map(|f| Tool {
                tool_type: "function".to_string(),
                function: f,
            })
            .collect();

        let request = ChatRequest {
            model: model_id.clone(),
            messages: vec![Message {
                role: "user".to_string(),
                content: Some(question.to_string()),
                tool_calls: None,
            }],
            tools,
            max_tokens: 500,
        };

        match ureq::post(&format!("{}/chat/completions", api_base_url))
            .set("Authorization", &format!("Bearer {}", api_key))
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(30))
            .send_json(&request)
        {
            Ok(response) => match response.into_json::<ChatResponse>() {
                Ok(data) => {
                    if let Some(tool_calls) = &data.choices[0].message.tool_calls {
                        if !tool_calls.is_empty() {
                            let func_name = &tool_calls[0].function.name;
                            let success = func_name == expected;
                            println!(
                                "结果: {} 调用了 {}\n",
                                if success { "✓" } else { "✗" },
                                func_name
                            );
                            results.push(success);
                        } else {
                            println!("结果: ✗ 未调用函数\n");
                            results.push(false);
                        }
                    } else {
                        println!("结果: ✗ 未调用函数\n");
                        results.push(false);
                    }
                }
                Err(e) => {
                    println!("结果: ✗ 解析错误: {}\n", e);
                    results.push(false);
                }
            },
            Err(e) => {
                println!("结果: ✗ API 错误: {}\n", e);
                results.push(false);
            }
        }
    }

    let passed = results.iter().filter(|&&r| r).count();
    println!("{}", "=".repeat(60));
    println!("测试结果: {}/{} 通过", passed, results.len());
    println!("{}", "=".repeat(60));
    println!();
}

fn main() {
    test_function_call();
}
