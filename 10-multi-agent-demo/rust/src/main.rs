use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;

#[derive(Serialize, Deserialize, Debug)]
struct Message {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    temperature: f32,
    max_tokens: i32,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: Message,
}

struct Agent {
    name: String,
    role: String,
}

struct TaskResult {
    success: bool,
    result: String,
    error: String,
}

impl Agent {
    fn new(name: &str, role: &str) -> Self {
        Agent {
            name: name.to_string(),
            role: role.to_string(),
        }
    }

    fn execute(&self, task: &str) -> TaskResult {
        println!("\n[{}] 开始执行任务", self.name);
        println!("角色: {}", self.role);
        println!("任务: {}\n", task);

        let api_base_url = env::var("API_BASE_URL").unwrap();
        let api_key = env::var("API_KEY").unwrap();
        let model_id = env::var("MODEL_ID").unwrap();

        // 构建请求
        let request_body = ChatRequest {
            model: model_id,
            messages: vec![Message {
                role: "user".to_string(),
                content: format!("{}\n任务：{}", self.role, task),
            }],
            temperature: 0.3,
            max_tokens: 200,
        };

        println!("  📤 发送请求...");

        // 使用 ureq 发送请求
        let response = ureq::post(&format!("{}/chat/completions", api_base_url))
            .set("Authorization", &format!("Bearer {}", api_key))
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(60))
            .send_json(&request_body);

        match response {
            Ok(resp) => {
                println!("  📥 收到响应");

                match resp.into_json::<ChatResponse>() {
                    Ok(chat_resp) => {
                        println!("  ✓ 完成\n");
                        TaskResult {
                            success: true,
                            result: chat_resp.choices[0].message.content.clone(),
                            error: String::new(),
                        }
                    }
                    Err(e) => {
                        println!("  ✗ 解析失败: {}", e);
                        TaskResult {
                            success: false,
                            result: String::new(),
                            error: format!("解析响应失败: {}", e),
                        }
                    }
                }
            }
            Err(e) => {
                println!("  ✗ 请求失败: {}", e);
                TaskResult {
                    success: false,
                    result: String::new(),
                    error: e.to_string(),
                }
            }
        }
    }
}

struct WorkflowStep {
    id: String,
    agent: String,
    task: String,
}

fn main() {
    // 加载环境变量
    dotenv::from_filename("../.env").ok();

    println!("============================================================");
    println!("Multi-Agent 协作演示（Rust 版本）");
    println!("============================================================\n");

    // 创建 Agents
    let coder = Agent::new("Coder", "Python 代码生成专家");
    let tester = Agent::new("Tester", "测试用例生成专家");
    let reviewer = Agent::new("Reviewer", "代码审查专家");

    let mut agents: HashMap<String, Agent> = HashMap::new();
    agents.insert("Coder".to_string(), coder);
    agents.insert("Tester".to_string(), tester);
    agents.insert("Reviewer".to_string(), reviewer);

    println!("✓ 注册 Agent: Coder");
    println!("✓ 注册 Agent: Tester");
    println!("✓ 注册 Agent: Reviewer\n");

    // 定义工作流
    let workflow = vec![
        WorkflowStep {
            id: "generate_code".to_string(),
            agent: "Coder".to_string(),
            task: "写一个 Python 函数 fibonacci(n)。只要代码。".to_string(),
        },
        WorkflowStep {
            id: "generate_tests".to_string(),
            agent: "Tester".to_string(),
            task: "写 3 个测试 fibonacci(0), fibonacci(1), fibonacci(5)。只要代码。".to_string(),
        },
        WorkflowStep {
            id: "review_code".to_string(),
            agent: "Reviewer".to_string(),
            task: "说一个优点。".to_string(),
        },
    ];

    println!("============================================================");
    println!("开始执行 Multi-Agent 工作流");
    println!("============================================================");

    // 执行工作流
    let mut results: HashMap<String, TaskResult> = HashMap::new();

    for step in &workflow {
        if let Some(agent) = agents.get(&step.agent) {
            let result = agent.execute(&step.task);

            if !result.success {
                println!("✗ 工作流失败: {}", result.error);
                results.insert(step.id.clone(), result);
                break;
            }

            results.insert(step.id.clone(), result);
        }
    }

    println!("\n============================================================");
    println!("工作流执行完成");
    println!("============================================================\n");

    // 显示结果
    println!("============================================================");
    println!("最终结果");
    println!("============================================================\n");

    for step in &workflow {
        if let Some(result) = results.get(&step.id) {
            if result.success {
                println!("[{}]", step.id);
                // 安全地截断 UTF-8 字符串
                if result.result.len() > 200 {
                    let mut end = 200;
                    while end > 0 && !result.result.is_char_boundary(end) {
                        end -= 1;
                    }
                    println!("{}...\n", &result.result[..end]);
                } else {
                    println!("{}\n", result.result);
                }
            }
        }
    }

    // Multi-Agent 的价值
    println!("============================================================");
    println!("Multi-Agent 的价值");
    println!("============================================================\n");

    println!("vs 单个 Agent:");
    println!("  单个 Agent:");
    println!("    - 需要处理所有任务");
    println!("    - 容易出错");
    println!("    - 难以优化\n");

    println!("  Multi-Agent:");
    println!("    ✓ 专业分工");
    println!("    ✓ 每个 Agent 专注自己的领域");
    println!("    ✓ 结果更可靠");
    println!("    ✓ 易于扩展\n");

    println!("结论:");
    println!("  Multi-Agent 适合复杂任务");
    println!("  通过协作提高质量\n");
}
