use colored::*;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;

#[derive(Serialize)]
struct Message {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ResponseFormat {
    #[serde(rename = "type")]
    format_type: String,
    json_schema: JSONSchema,
}

#[derive(Serialize)]
struct JSONSchema {
    name: String,
    schema: serde_json::Value,
    strict: bool,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<ResponseFormat>,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: MessageResponse,
}

#[derive(Deserialize)]
struct MessageResponse {
    content: String,
}

fn normal_json_output(api_url: &str, api_key: &str, model: &str, prompt: &str) {
    println!("{}❌ 普通 JSON 输出（不保证格式）:{}\n", "".yellow(), "".clear());

    let request = ChatRequest {
        model: model.to_string(),
        messages: vec![
            Message {
                role: "system".to_string(),
                content: "你是一个数据提取助手。请以 JSON 格式返回结果。".to_string(),
            },
            Message {
                role: "user".to_string(),
                content: prompt.to_string(),
            },
        ],
        response_format: None,
    };

    let url = format!("{}/chat/completions", api_url);
    let response = ureq::post(&url)
        .set("Authorization", &format!("Bearer {}", api_key))
        .set("Content-Type", "application/json")
        .send_json(&request);

    match response {
        Ok(resp) => {
            if let Ok(chat_resp) = resp.into_json::<ChatResponse>() {
                let content = &chat_resp.choices[0].message.content;
                println!("{}输出:{}\n{}\n", "".cyan(), "".clear(), content);

                // 尝试解析 JSON
                match serde_json::from_str::<serde_json::Value>(content) {
                    Ok(result) => {
                        println!("{}✓ JSON 解析成功{}", "".green(), "".clear());
                        println!(
                            "解析结果: {}\n",
                            serde_json::to_string_pretty(&result).unwrap()
                        );
                    }
                    Err(e) => {
                        println!("{}✗ JSON 解析失败: {}{}\n", "".red(), e, "".clear());
                    }
                }
            }
        }
        Err(e) => {
            println!("{}错误: {}{}", "".red(), e, "".clear());
        }
    }
}

fn structured_output(
    api_url: &str,
    api_key: &str,
    model: &str,
    prompt: &str,
    schema: serde_json::Value,
) {
    println!("{}✅ 结构化输出（保证格式）:{}\n", "".yellow(), "".clear());

    let request = ChatRequest {
        model: model.to_string(),
        messages: vec![
            Message {
                role: "system".to_string(),
                content: "你是一个数据提取助手。".to_string(),
            },
            Message {
                role: "user".to_string(),
                content: prompt.to_string(),
            },
        ],
        response_format: Some(ResponseFormat {
            format_type: "json_schema".to_string(),
            json_schema: JSONSchema {
                name: "user_info".to_string(),
                schema,
                strict: true,
            },
        }),
    };

    let url = format!("{}/chat/completions", api_url);
    let response = ureq::post(&url)
        .set("Authorization", &format!("Bearer {}", api_key))
        .set("Content-Type", "application/json")
        .send_json(&request);

    match response {
        Ok(resp) => {
            if let Ok(chat_resp) = resp.into_json::<ChatResponse>() {
                let content = &chat_resp.choices[0].message.content;
                println!("{}输出:{}\n{}\n", "".cyan(), "".clear(), content);

                // 解析 JSON
                match serde_json::from_str::<serde_json::Value>(content) {
                    Ok(result) => {
                        println!(
                            "{}✓ JSON 解析成功（格式保证正确）{}",
                            "".green(),
                            "".clear()
                        );
                        println!(
                            "解析结果: {}\n",
                            serde_json::to_string_pretty(&result).unwrap()
                        );
                    }
                    Err(e) => {
                        println!("{}✗ JSON 解析失败: {}{}\n", "".red(), e, "".clear());
                    }
                }
            }
        }
        Err(e) => {
            println!("{}错误: {}{}", "".red(), e, "".clear());
        }
    }
}

fn main() {
    dotenv::from_filename("../.env").ok();

    let api_url = env::var("API_BASE_URL").expect("API_BASE_URL not set");
    let api_key = env::var("API_KEY").expect("API_KEY not set");
    let model = env::var("MODEL_ID").expect("MODEL_ID not set");

    println!("{}{}", "".cyan(), "=".repeat(60));
    println!("结构化输出 vs 普通 JSON 对比");
    println!("{}{}\n", "=".repeat(60), "".clear());

    // 定义 JSON Schema
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "姓名"
            },
            "age": {
                "type": "integer",
                "description": "年龄"
            },
            "position": {
                "type": "string",
                "description": "职位"
            },
            "email": {
                "type": "string",
                "description": "邮箱"
            },
            "skills": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "技能列表"
            }
        },
        "required": ["name", "age", "position", "email"],
        "additionalProperties": false
    });

    let prompt = "从以下文本中提取信息：张三，28岁，Python工程师，邮箱zhangsan@example.com，擅长Django和FastAPI";

    println!("{}任务:{} {}\n", "".green(), "".clear(), prompt);
    println!("{}{}{}\n", "".cyan(), "-".repeat(60), "".clear());

    // 普通 JSON 输出
    normal_json_output(&api_url, &api_key, &model, prompt);

    println!("{}{}{}\n", "".cyan(), "-".repeat(60), "".clear());

    // 结构化输出
    structured_output(&api_url, &api_key, &model, prompt, schema);

    // 对比总结
    println!("{}{}", "".cyan(), "=".repeat(60));
    println!("对比总结");
    println!("{}{}\n", "=".repeat(60), "".clear());

    println!("{}普通 JSON 输出:{}", "".yellow(), "".clear());
    println!("  问题:");
    println!("    - 可能包含 markdown 格式");
    println!("    - 可能有额外的说明文字");
    println!("    - 字段名可能不一致");
    println!("    - 类型可能不匹配（如年龄是字符串）");
    println!("    - 可能缺少必需字段\n");

    println!("{}结构化输出:{}", "".yellow(), "".clear());
    println!("  优势:");
    println!("    ✓ 100% 符合 JSON Schema");
    println!("    ✓ 纯 JSON，无额外格式");
    println!("    ✓ 字段名严格匹配");
    println!("    ✓ 类型严格匹配");
    println!("    ✓ 必需字段保证存在");
    println!("    ✓ 可以禁止额外字段\n");

    println!("{}结论:{}", "".green(), "".clear());
    println!("  结构化输出是生产环境的最佳选择");
    println!("  特别适合需要严格格式的场景\n");
}
