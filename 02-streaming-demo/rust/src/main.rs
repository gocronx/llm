use colored::*;
use serde::{Deserialize, Serialize};
use std::env;
use std::io::{BufRead, BufReader};
use std::time::Instant;

#[derive(Serialize, Deserialize)]
struct Message {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    stream: bool,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: MessageContent,
}

#[derive(Deserialize)]
struct MessageContent {
    content: String,
}

#[derive(Deserialize)]
struct StreamChunk {
    choices: Vec<StreamChoice>,
}

#[derive(Deserialize)]
struct StreamChoice {
    delta: Delta,
}

#[derive(Deserialize)]
struct Delta {
    #[serde(default)]
    content: String,
}

fn non_streaming_request(api_url: &str, api_key: &str, model: &str, prompt: &str) {
    println!("{}非流式输出（等待完整响应）:{}\n", "".yellow(), "".clear());

    let start_time = Instant::now();

    let request = ChatRequest {
        model: model.to_string(),
        messages: vec![Message {
            role: "user".to_string(),
            content: prompt.to_string(),
        }],
        stream: false,
    };

    let url = format!("{}/chat/completions", api_url);
    let response = ureq::post(&url)
        .set("Authorization", &format!("Bearer {}", api_key))
        .set("Content-Type", "application/json")
        .send_json(&request);

    let wait_time = start_time.elapsed().as_secs_f64();

    match response {
        Ok(resp) => {
            if let Ok(chat_resp) = resp.into_json::<ChatResponse>() {
                println!("{}[等待 {:.1}秒]{}", "".cyan(), wait_time, "".clear());
                if let Some(choice) = chat_resp.choices.first() {
                    println!("{}", choice.message.content);
                }
            }
        }
        Err(e) => {
            println!("{}错误: {}{}", "".red(), e, "".clear());
        }
    }
}

fn streaming_request(api_url: &str, api_key: &str, model: &str, prompt: &str) {
    println!("\n{}流式输出（逐字显示）:{}\n", "".yellow(), "".clear());

    let start_time = Instant::now();
    let mut first_token_time: Option<f64> = None;
    let mut token_count = 0;

    let request = ChatRequest {
        model: model.to_string(),
        messages: vec![Message {
            role: "user".to_string(),
            content: prompt.to_string(),
        }],
        stream: true,
    };

    let url = format!("{}/chat/completions", api_url);
    let response = ureq::post(&url)
        .set("Authorization", &format!("Bearer {}", api_key))
        .set("Content-Type", "application/json")
        .timeout(std::time::Duration::from_secs(60))
        .send_json(&request);

    match response {
        Ok(resp) => {
            let reader = BufReader::new(resp.into_reader());

            for line in reader.lines() {
                if let Ok(line) = line {
                    let line = line.trim();
                    if !line.starts_with("data: ") {
                        continue;
                    }

                    let data = &line[6..];
                    if data == "[DONE]" {
                        break;
                    }

                    if let Ok(chunk) = serde_json::from_str::<StreamChunk>(data) {
                        if let Some(choice) = chunk.choices.first() {
                            let content = &choice.delta.content;
                            if !content.is_empty() {
                                if first_token_time.is_none() {
                                    first_token_time = Some(start_time.elapsed().as_secs_f64());
                                }
                                print!("{}", content);
                                token_count += 1;
                            }
                        }
                    }
                }
            }

            println!(); // 换行

            let total_time = start_time.elapsed().as_secs_f64();
            if let Some(first_time) = first_token_time {
                println!(
                    "\n{}[首字时间: {:.1}秒, 总时间: {:.1}秒, Token数: {}]{}",
                    "".cyan(),
                    first_time,
                    total_time,
                    token_count,
                    "".clear()
                );
            }
        }
        Err(e) => {
            println!("{}错误: {}{}", "".red(), e, "".clear());
        }
    }
}

fn main() {
    // 加载环境变量
    dotenv::from_filename("../.env").ok();

    let api_url = env::var("API_BASE_URL").expect("API_BASE_URL not set");
    let api_key = env::var("API_KEY").expect("API_KEY not set");
    let model = env::var("MODEL_ID").expect("MODEL_ID not set");

    println!("{}{}", "".cyan(), "=".repeat(60));
    println!("Streaming 对比演示");
    println!("{}{}\n", "=".repeat(60), "".clear());

    let prompt = "请写一个关于人工智能的简短介绍，包括定义、应用和未来发展。";

    println!("{}问题:{} {}\n", "".green(), "".clear(), prompt);
    println!("{}{}{}\n", "".cyan(), "-".repeat(60), "".clear());

    // 非流式
    non_streaming_request(&api_url, &api_key, &model, prompt);

    println!("\n{}{}{}", "".cyan(), "-".repeat(60), "".clear());

    // 流式
    streaming_request(&api_url, &api_key, &model, prompt);

    // 总结
    println!("\n{}{}", "".cyan(), "=".repeat(60));
    println!("对比总结");
    println!("{}{}\n", "=".repeat(60), "".clear());

    println!("{}非流式输出:{}", "".yellow(), "".clear());
    println!("  优点: 实现简单");
    println!("  缺点: 用户需要等待完整响应（5-10秒）");
    println!("       感觉很慢，体验差\n");

    println!("{}流式输出:{}", "".yellow(), "".clear());
    println!("  优点: 立即开始显示（0.5-1秒）");
    println!("       用户感觉很快，体验好");
    println!("  缺点: 实现稍复杂\n");

    println!("{}结论:{}", "".green(), "".clear());
    println!("  生产环境必须使用流式输出！");
    println!("  用户体验差异巨大。\n");
}
