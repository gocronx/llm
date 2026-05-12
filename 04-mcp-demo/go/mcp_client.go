package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/joho/godotenv"
)

const (
	ColorReset  = "\033[0m"
	ColorCyan   = "\033[36m"
	ColorYellow = "\033[33m"
	ColorGreen  = "\033[32m"
)

type Message struct {
	Role       string      `json:"role"`
	Content    string      `json:"content,omitempty"`
	ToolCalls  []ToolCall  `json:"tool_calls,omitempty"`
	ToolCallID string      `json:"tool_call_id,omitempty"`
}

type ToolCall struct {
	ID       string   `json:"id"`
	Type     string   `json:"type"`
	Function Function `json:"function"`
}

type Function struct {
	Name      string `json:"name"`
	Arguments string `json:"arguments"`
}

type Tool struct {
	Type     string       `json:"type"`
	Function ToolFunction `json:"function"`
}

type ToolFunction struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  map[string]interface{} `json:"parameters"`
}

type ChatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
	Tools    []Tool    `json:"tools"`
}

type ChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

type MCPClient struct {
	apiURL  string
	apiKey  string
	model   string
	tools   []Tool
	basePath string
}

func NewMCPClient(apiURL, apiKey, model, basePath string) *MCPClient {
	return &MCPClient{
		apiURL:   apiURL,
		apiKey:   apiKey,
		model:    model,
		basePath: basePath,
		tools:    make([]Tool, 0),
	}
}

func (c *MCPClient) RegisterTools() {
	c.tools = []Tool{
		{
			Type: "function",
			Function: ToolFunction{
				Name:        "read_file",
				Description: "读取文件内容",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"path": map[string]interface{}{
							"type":        "string",
							"description": "文件路径",
						},
					},
					"required": []string{"path"},
				},
			},
		},
		{
			Type: "function",
			Function: ToolFunction{
				Name:        "write_file",
				Description: "写入文件内容",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"path": map[string]interface{}{
							"type":        "string",
							"description": "文件路径",
						},
						"content": map[string]interface{}{
							"type":        "string",
							"description": "文件内容",
						},
					},
					"required": []string{"path", "content"},
				},
			},
		},
		{
			Type: "function",
			Function: ToolFunction{
				Name:        "list_directory",
				Description: "列出目录内容",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"path": map[string]interface{}{
							"type":        "string",
							"description": "目录路径",
							"default":     ".",
						},
					},
				},
			},
		},
	}
}

func (c *MCPClient) CallTool(name string, arguments map[string]interface{}) string {
	switch name {
	case "read_file":
		return c.readFile(arguments["path"].(string))
	case "write_file":
		return c.writeFile(arguments["path"].(string), arguments["content"].(string))
	case "list_directory":
		path := "."
		if p, ok := arguments["path"]; ok {
			path = p.(string)
		}
		return c.listDirectory(path)
	default:
		return fmt.Sprintf("未知工具: %s", name)
	}
}

func (c *MCPClient) readFile(path string) string {
	fullPath := c.basePath + "/" + path
	content, err := os.ReadFile(fullPath)
	if err != nil {
		return fmt.Sprintf("读取失败: %v", err)
	}
	return string(content)
}

func (c *MCPClient) writeFile(path, content string) string {
	fullPath := c.basePath + "/" + path
	err := os.WriteFile(fullPath, []byte(content), 0644)
	if err != nil {
		return fmt.Sprintf("写入失败: %v", err)
	}
	return fmt.Sprintf("成功写入文件: %s", path)
}

func (c *MCPClient) listDirectory(path string) string {
	fullPath := c.basePath + "/" + path
	entries, err := os.ReadDir(fullPath)
	if err != nil {
		return fmt.Sprintf("列出目录失败: %v", err)
	}

	var result strings.Builder
	for _, entry := range entries {
		if entry.IsDir() {
			result.WriteString(fmt.Sprintf("📁 %s/\n", entry.Name()))
		} else {
			info, _ := entry.Info()
			result.WriteString(fmt.Sprintf("📄 %s (%d bytes)\n", entry.Name(), info.Size()))
		}
	}

	if result.Len() == 0 {
		return "目录为空"
	}
	return result.String()
}

func (c *MCPClient) Chat(messages []Message, maxRounds int) string {
	for round := 1; round <= maxRounds; round++ {
		fmt.Printf("\n%s--- 第 %d 轮 ---%s\n\n", ColorCyan, round, ColorReset)

		reqBody := ChatRequest{
			Model:    c.model,
			Messages: messages,
			Tools:    c.tools,
		}

		jsonData, _ := json.Marshal(reqBody)
		req, _ := http.NewRequest("POST", c.apiURL+"/chat/completions", bytes.NewBuffer(jsonData))
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
		req.Header.Set("Content-Type", "application/json")

		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			return fmt.Sprintf("API 错误: %v", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != 200 {
			return fmt.Sprintf("API 错误: %d", resp.StatusCode)
		}

		body, _ := io.ReadAll(resp.Body)
		var chatResp ChatResponse
		json.Unmarshal(body, &chatResp)

		message := chatResp.Choices[0].Message

		if len(message.ToolCalls) > 0 {
			messages = append(messages, message)

			for _, toolCall := range message.ToolCalls {
				var args map[string]interface{}
				json.Unmarshal([]byte(toolCall.Function.Arguments), &args)

				fmt.Printf("%s🔧 调用工具:%s %s\n", ColorYellow, ColorReset, toolCall.Function.Name)
				fmt.Printf("%s   参数:%s %s\n", ColorYellow, ColorReset, toolCall.Function.Arguments)

				result := c.CallTool(toolCall.Function.Name, args)
				if len(result) > 100 {
					fmt.Printf("%s   结果:%s %s...\n", ColorYellow, ColorReset, result[:100])
				} else {
					fmt.Printf("%s   结果:%s %s\n", ColorYellow, ColorReset, result)
				}

				messages = append(messages, Message{
					Role:       "tool",
					ToolCallID: toolCall.ID,
					Content:    result,
				})
			}
			continue
		}

		fmt.Printf("\n%s✅ 最终答案:%s\n\n", ColorGreen, ColorReset)
		return message.Content
	}

	return "达到最大轮数限制"
}

func main() {
	if err := godotenv.Load("../.env"); err != nil {
		log.Fatal("Error loading .env file")
	}

	apiURL := os.Getenv("API_BASE_URL")
	apiKey := os.Getenv("API_KEY")
	model := os.Getenv("MODEL_ID")

	fmt.Printf("%s%s\n", ColorCyan, strings.Repeat("=", 60))
	fmt.Println("MCP (Model Context Protocol) 演示")
	fmt.Printf("%s%s\n\n", strings.Repeat("=", 60), ColorReset)

	basePath := "test_workspace"
	os.MkdirAll(basePath, 0755)

	client := NewMCPClient(apiURL, apiKey, model, basePath)
	client.RegisterTools()

	fmt.Printf("%s场景:%s 让 AI 创建一个 TODO 列表文件\n\n", ColorGreen, ColorReset)
	fmt.Printf("%s%s%s\n\n", ColorCyan, strings.Repeat("-", 60), ColorReset)

	messages := []Message{
		{
			Role:    "user",
			Content: "请帮我创建一个 todo.txt 文件，内容包括：1. 学习 MCP 协议 2. 实现 MCP Server 3. 测试 MCP Client",
		},
	}

	result := client.Chat(messages, 5)
	fmt.Println(result)

	fmt.Printf("\n%s%s%s\n\n", ColorCyan, strings.Repeat("-", 60), ColorReset)

	fmt.Printf("%s验证:%s 检查文件是否创建成功\n\n", ColorGreen, ColorReset)

	messages2 := []Message{
		{
			Role:    "user",
			Content: "请列出当前目录的文件，然后读取 todo.txt 的内容",
		},
	}

	result2 := client.Chat(messages2, 5)
	fmt.Println(result2)

	fmt.Printf("\n%s%s\n", ColorCyan, strings.Repeat("=", 60))
	fmt.Println("MCP 的价值")
	fmt.Printf("%s%s\n\n", strings.Repeat("=", 60), ColorReset)

	fmt.Printf("%sMCP vs Function Call:%s\n\n", ColorYellow, ColorReset)
	fmt.Println("Function Call:")
	fmt.Println("  - 每个应用自己定义工具格式")
	fmt.Println("  - 没有统一标准")
	fmt.Println("  - 难以复用\n")

	fmt.Println("MCP:")
	fmt.Println("  - 统一的协议标准")
	fmt.Println("  - Server 可以被多个 Client 复用")
	fmt.Println("  - 生态系统更健康\n")

	fmt.Printf("%s结论:%s\n", ColorGreen, ColorReset)
	fmt.Println("  MCP 是 Function Call 的标准化演进")
	fmt.Println("  长期价值更高\n")
}
