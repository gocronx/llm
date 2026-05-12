use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Message {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    max_tokens: i32,
    temperature: f32,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: Message,
}

fn call_llm(messages: &[Message], max_tokens: i32) -> Result<String, Box<dyn std::error::Error>> {
    let api_base_url = env::var("API_BASE_URL")?;
    let api_key = env::var("API_KEY")?;
    let model_id = env::var("MODEL_ID")?;

    let request = ChatRequest {
        model: model_id,
        messages: messages.to_vec(),
        max_tokens,
        temperature: 0.7,
    };

    let response: ChatResponse = ureq::post(&format!("{}/chat/completions", api_base_url))
        .set("Authorization", &format!("Bearer {}", api_key))
        .send_json(&request)?
        .into_json()?;

    Ok(response.choices[0].message.content.clone())
}

fn estimate_tokens(text: &str) -> usize {
    let chinese_chars = text.chars().filter(|c| *c >= '\u{4e00}' && *c <= '\u{9fff}').count();
    let other_chars = text.chars().count() - chinese_chars;
    ((chinese_chars as f64 / 1.5) + (other_chars as f64 / 4.0)) as usize
}

fn print_memory_info(messages: &[Message], strategy_name: &str) {
    let total_text: String = messages.iter().map(|m| m.content.as_str()).collect::<Vec<_>>().join(" ");
    let tokens = estimate_tokens(&total_text);
    
    println!("\n\x1b[36m[{}] 记忆状态\x1b[0m", strategy_name);
    println!("  消息数量: {}", messages.len());
    println!("  估算 Token: {}", tokens);
    println!("  成本估算: ~${:.6} (假设 $0.01/1K tokens)", tokens as f64 * 0.00001);
}

// ============================================================
// 策略 1: 完整记忆
// ============================================================

struct FullMemoryChat {
    messages: Vec<Message>,
    system_prompt: Message,
}

impl FullMemoryChat {
    fn new() -> Self {
        Self {
            messages: Vec::new(),
            system_prompt: Message {
                role: "system".to_string(),
                content: "你是一个友好的助手。用简短的1-2句话回答问题。".to_string(),
            },
        }
    }

    fn chat(&mut self, user_input: &str) -> Result<String, Box<dyn std::error::Error>> {
        self.messages.push(Message {
            role: "user".to_string(),
            content: user_input.to_string(),
        });

        let mut request_messages = vec![self.system_prompt.clone()];
        request_messages.extend(self.messages.clone());

        let response = call_llm(&request_messages, 150)?;

        self.messages.push(Message {
            role: "assistant".to_string(),
            content: response.clone(),
        });

        Ok(response)
    }

    fn get_memory_info(&self) {
        let mut all_messages = vec![self.system_prompt.clone()];
        all_messages.extend(self.messages.clone());
        print_memory_info(&all_messages, "完整记忆");
    }
}

// ============================================================
// 策略 2: 滑动窗口
// ============================================================

struct SlidingWindowChat {
    messages: Vec<Message>,
    window_size: usize,
    system_prompt: Message,
}

impl SlidingWindowChat {
    fn new(window_size: usize) -> Self {
        Self {
            messages: Vec::new(),
            window_size,
            system_prompt: Message {
                role: "system".to_string(),
                content: "你是一个友好的助手。用简短的1-2句话回答问题。".to_string(),
            },
        }
    }

    fn chat(&mut self, user_input: &str) -> Result<String, Box<dyn std::error::Error>> {
        self.messages.push(Message {
            role: "user".to_string(),
            content: user_input.to_string(),
        });

        if self.messages.len() > self.window_size {
            self.messages = self.messages[self.messages.len() - self.window_size..].to_vec();
        }

        let mut request_messages = vec![self.system_prompt.clone()];
        request_messages.extend(self.messages.clone());

        let response = call_llm(&request_messages, 150)?;

        self.messages.push(Message {
            role: "assistant".to_string(),
            content: response.clone(),
        });

        if self.messages.len() > self.window_size {
            self.messages = self.messages[self.messages.len() - self.window_size..].to_vec();
        }

        Ok(response)
    }

    fn get_memory_info(&self) {
        let mut all_messages = vec![self.system_prompt.clone()];
        all_messages.extend(self.messages.clone());
        print_memory_info(&all_messages, "滑动窗口");
        println!("  窗口大小: {}", self.window_size);
    }
}

// ============================================================
// 策略 3: Token 限制
// ============================================================

struct TokenLimitedChat {
    messages: Vec<Message>,
    max_tokens: usize,
    system_prompt: Message,
}

impl TokenLimitedChat {
    fn new(max_tokens: usize) -> Self {
        Self {
            messages: Vec::new(),
            max_tokens,
            system_prompt: Message {
                role: "system".to_string(),
                content: "你是一个友好的助手。用简短的1-2句话回答问题。".to_string(),
            },
        }
    }

    fn chat(&mut self, user_input: &str) -> Result<String, Box<dyn std::error::Error>> {
        self.messages.push(Message {
            role: "user".to_string(),
            content: user_input.to_string(),
        });

        self.trim_by_tokens();

        let mut request_messages = vec![self.system_prompt.clone()];
        request_messages.extend(self.messages.clone());

        let response = call_llm(&request_messages, 150)?;

        self.messages.push(Message {
            role: "assistant".to_string(),
            content: response.clone(),
        });

        self.trim_by_tokens();

        Ok(response)
    }

    fn trim_by_tokens(&mut self) {
        while self.messages.len() > 2 {
            let mut total_text = self.system_prompt.content.clone();
            total_text.push(' ');
            for m in &self.messages {
                total_text.push_str(&m.content);
                total_text.push(' ');
            }

            let tokens = estimate_tokens(&total_text);
            if tokens <= self.max_tokens {
                break;
            }

            self.messages.remove(0);
        }
    }

    fn get_memory_info(&self) {
        let mut all_messages = vec![self.system_prompt.clone()];
        all_messages.extend(self.messages.clone());
        print_memory_info(&all_messages, "Token 限制");
        println!("  Token 限制: {}", self.max_tokens);
    }
}

// ============================================================
// 主演示
// ============================================================

fn truncate(s: &str, max_len: usize) -> String {
    if s.chars().count() <= max_len {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max_len).collect();
        format!("{}...", truncated)
    }
}

fn demo_full_memory(conversations: &[&str]) {
    println!("\n\x1b[36m{}\n{}\n{}\x1b[0m\n", "=".repeat(60), "策略 1: 完整记忆（Full Memory）", "=".repeat(60));

    let mut chat = FullMemoryChat::new();

    for (i, user_input) in conversations.iter().enumerate() {
        println!("\n\x1b[32m[轮次 {}] 用户:\x1b[0m {}", i + 1, user_input);
        match chat.chat(user_input) {
            Ok(response) => {
                println!("\x1b[34m助手:\x1b[0m {}", truncate(&response, 150));
                chat.get_memory_info();
            }
            Err(e) => println!("错误: {}", e),
        }
    }
}

fn demo_sliding_window(conversations: &[&str]) {
    println!("\n\x1b[36m{}\n{}\n{}\x1b[0m\n", "=".repeat(60), "策略 2: 滑动窗口（Sliding Window, 窗口=4）", "=".repeat(60));

    let mut chat = SlidingWindowChat::new(4);

    for (i, user_input) in conversations.iter().enumerate() {
        println!("\n\x1b[32m[轮次 {}] 用户:\x1b[0m {}", i + 1, user_input);
        match chat.chat(user_input) {
            Ok(response) => {
                println!("\x1b[34m助手:\x1b[0m {}", truncate(&response, 150));
                chat.get_memory_info();
            }
            Err(e) => println!("错误: {}", e),
        }
    }
}

fn demo_token_limited(conversations: &[&str]) {
    println!("\n\x1b[36m{}\n{}\n{}\x1b[0m\n", "=".repeat(60), "策略 3: Token 限制（Token-Limited, 限制=300）", "=".repeat(60));

    let mut chat = TokenLimitedChat::new(300);

    for (i, user_input) in conversations.iter().enumerate() {
        println!("\n\x1b[32m[轮次 {}] 用户:\x1b[0m {}", i + 1, user_input);
        match chat.chat(user_input) {
            Ok(response) => {
                println!("\x1b[34m助手:\x1b[0m {}", truncate(&response, 150));
                chat.get_memory_info();
            }
            Err(e) => println!("错误: {}", e),
        }
    }
}

fn main() {
    dotenv::from_path("../.env").ok();

    println!("\x1b[36m{}\n对话记忆管理策略演示\n{}\x1b[0m\n", "=".repeat(60), "=".repeat(60));

    let conversations = vec![
        "你好，我叫张三",
        "我今年 25 岁",
        "我喜欢编程",
        "我刚才说我叫什么名字？",
        "我多大了？",
        "我有什么爱好？",
    ];

    println!("\x1b[33m测试对话序列:\x1b[0m");
    for (i, conv) in conversations.iter().enumerate() {
        println!("  {}. {}", i + 1, conv);
    }

    // 策略 1: 完整记忆
    demo_full_memory(&conversations);

    // 策略 2: 滑动窗口
    demo_sliding_window(&conversations);

    // 策略 3: Token 限制
    demo_token_limited(&conversations);

    // 总结
    println!("\n\x1b[36m{}\n策略对比总结\n{}\x1b[0m\n", "=".repeat(60), "=".repeat(60));

    println!("\x1b[33m1. 完整记忆\x1b[0m");
    println!("  ✅ 优点: 记住所有信息，上下文完整");
    println!("  ❌ 缺点: Token 消耗大，成本高");
    println!("  📌 适用: 短对话、重要对话\n");

    println!("\x1b[33m2. 滑动窗口\x1b[0m");
    println!("  ✅ 优点: Token 可控，实现简单");
    println!("  ❌ 缺点: 会忘记早期信息");
    println!("  📌 适用: 一般对话、成本敏感场景\n");

    println!("\x1b[33m3. Token 限制\x1b[0m");
    println!("  ✅ 优点: 精确控制成本");
    println!("  ❌ 缺点: 可能在对话中途突然'失忆'");
    println!("  📌 适用: 严格成本控制场景\n");

    println!("\x1b[32m建议:\x1b[0m");
    println!("  - 短对话（<10 轮）：完整记忆");
    println!("  - 一般对话（10-50 轮）：滑动窗口");
    println!("  - 成本敏感：Token 限制\n");
}
