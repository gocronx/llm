package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"github.com/joho/godotenv"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Model       string    `json:"model"`
	Messages    []Message `json:"messages"`
	Temperature float64   `json:"temperature"`
	MaxTokens   int       `json:"max_tokens"`
}

type ChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

type Agent struct {
	Name string
	Role string
}

type TaskResult struct {
	Success bool
	Result  string
	Error   string
}

func (a *Agent) Execute(task string) TaskResult {
	fmt.Printf("\n[%s] 开始执行任务\n", a.Name)
	fmt.Printf("角色: %s\n", a.Role)
	fmt.Printf("任务: %s\n\n", task)

	apiBaseURL := os.Getenv("API_BASE_URL")
	apiKey := os.Getenv("API_KEY")
	modelID := os.Getenv("MODEL_ID")

	// 构建请求
	reqBody := ChatRequest{
		Model: modelID,
		Messages: []Message{
			{
				Role:    "user",
				Content: fmt.Sprintf("%s\n任务：%s", a.Role, task),
			},
		},
		Temperature: 0.3,
		MaxTokens:   200,
	}

	jsonData, _ := json.Marshal(reqBody)

	fmt.Println("  📤 发送请求...")

	req, _ := http.NewRequest("POST", apiBaseURL+"/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("  ✗ 请求失败: %v\n", err)
		return TaskResult{Success: false, Error: err.Error()}
	}
	defer resp.Body.Close()

	fmt.Println("  📥 收到响应")

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return TaskResult{Success: false, Error: fmt.Sprintf("API 错误: %d - %s", resp.StatusCode, string(body))}
	}

	var chatResp ChatResponse
	json.NewDecoder(resp.Body).Decode(&chatResp)

	fmt.Println("  ✓ 完成\n")

	return TaskResult{
		Success: true,
		Result:  chatResp.Choices[0].Message.Content,
	}
}

type WorkflowStep struct {
	ID    string
	Agent string
	Task  string
}

func main() {
	// 加载环境变量
	godotenv.Load("../.env")

	fmt.Println("============================================================")
	fmt.Println("Multi-Agent 协作演示（Go 版本）")
	fmt.Println("============================================================\n")

	// 创建 Agents
	coder := Agent{Name: "Coder", Role: "Python 代码生成专家"}
	tester := Agent{Name: "Tester", Role: "测试用例生成专家"}
	reviewer := Agent{Name: "Reviewer", Role: "代码审查专家"}

	agents := map[string]*Agent{
		"Coder":    &coder,
		"Tester":   &tester,
		"Reviewer": &reviewer,
	}

	fmt.Println("✓ 注册 Agent: Coder")
	fmt.Println("✓ 注册 Agent: Tester")
	fmt.Println("✓ 注册 Agent: Reviewer\n")

	// 定义工作流
	workflow := []WorkflowStep{
		{ID: "generate_code", Agent: "Coder", Task: "写一个 Python 函数 fibonacci(n)。只要代码。"},
		{ID: "generate_tests", Agent: "Tester", Task: "写 3 个测试 fibonacci(0), fibonacci(1), fibonacci(5)。只要代码。"},
		{ID: "review_code", Agent: "Reviewer", Task: "说一个优点。"},
	}

	fmt.Println("============================================================")
	fmt.Println("开始执行 Multi-Agent 工作流")
	fmt.Println("============================================================")

	// 执行工作流
	results := make(map[string]TaskResult)

	for _, step := range workflow {
		agent := agents[step.Agent]
		result := agent.Execute(step.Task)
		results[step.ID] = result

		if !result.Success {
			fmt.Printf("✗ 工作流失败: %s\n", result.Error)
			break
		}
	}

	fmt.Println("\n============================================================")
	fmt.Println("工作流执行完成")
	fmt.Println("============================================================\n")

	// 显示结果
	fmt.Println("============================================================")
	fmt.Println("最终结果")
	fmt.Println("============================================================\n")

	for _, step := range workflow {
		result := results[step.ID]
		if result.Success {
			fmt.Printf("[%s]\n", step.ID)
			if len(result.Result) > 200 {
				fmt.Printf("%s...\n\n", result.Result[:200])
			} else {
				fmt.Printf("%s\n\n", result.Result)
			}
		}
	}

	// Multi-Agent 的价值
	fmt.Println("============================================================")
	fmt.Println("Multi-Agent 的价值")
	fmt.Println("============================================================\n")

	fmt.Println("vs 单个 Agent:")
	fmt.Println("  单个 Agent:")
	fmt.Println("    - 需要处理所有任务")
	fmt.Println("    - 容易出错")
	fmt.Println("    - 难以优化\n")

	fmt.Println("  Multi-Agent:")
	fmt.Println("    ✓ 专业分工")
	fmt.Println("    ✓ 每个 Agent 专注自己的领域")
	fmt.Println("    ✓ 结果更可靠")
	fmt.Println("    ✓ 易于扩展\n")

	fmt.Println("结论:")
	fmt.Println("  Multi-Agent 适合复杂任务")
	fmt.Println("  通过协作提高质量\n")
}
