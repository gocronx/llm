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
	ColorRed    = "\033[31m"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ResponseFormat struct {
	Type       string     `json:"type"`
	JSONSchema JSONSchema `json:"json_schema"`
}

type JSONSchema struct {
	Name   string                 `json:"name"`
	Schema map[string]interface{} `json:"schema"`
	Strict bool                   `json:"strict"`
}

type ChatRequest struct {
	Model          string         `json:"model"`
	Messages       []Message      `json:"messages"`
	ResponseFormat ResponseFormat `json:"response_format,omitempty"`
}

type ChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

func normalJSONOutput(apiURL, apiKey, model, prompt string) {
	fmt.Printf("%s❌ 普通 JSON 输出（不保证格式）:%s\n\n", ColorYellow, ColorReset)

	reqBody := ChatRequest{
		Model: model,
		Messages: []Message{
			{Role: "system", Content: "你是一个数据提取助手。请以 JSON 格式返回结果。"},
			{Role: "user", Content: prompt},
		},
	}

	jsonData, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", apiURL+"/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("%s错误: %v%s\n", ColorRed, err, ColorReset)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == 200 {
		body, _ := io.ReadAll(resp.Body)
		var chatResp ChatResponse
		json.Unmarshal(body, &chatResp)

		content := chatResp.Choices[0].Message.Content
		fmt.Printf("%s输出:%s\n%s\n\n", ColorCyan, ColorReset, content)

		// 尝试解析 JSON
		var result map[string]interface{}
		if err := json.Unmarshal([]byte(content), &result); err == nil {
			fmt.Printf("%s✓ JSON 解析成功%s\n", ColorGreen, ColorReset)
			prettyJSON, _ := json.MarshalIndent(result, "", "  ")
			fmt.Printf("解析结果: %s\n\n", string(prettyJSON))
		} else {
			fmt.Printf("%s✗ JSON 解析失败: %v%s\n\n", ColorRed, err, ColorReset)
		}
	} else {
		fmt.Printf("%sAPI 错误: %d%s\n", ColorRed, resp.StatusCode, ColorReset)
	}
}

func structuredOutput(apiURL, apiKey, model, prompt string, schema map[string]interface{}) {
	fmt.Printf("%s✅ 结构化输出（保证格式）:%s\n\n", ColorYellow, ColorReset)

	reqBody := ChatRequest{
		Model: model,
		Messages: []Message{
			{Role: "system", Content: "你是一个数据提取助手。"},
			{Role: "user", Content: prompt},
		},
		ResponseFormat: ResponseFormat{
			Type: "json_schema",
			JSONSchema: JSONSchema{
				Name:   "user_info",
				Schema: schema,
				Strict: true,
			},
		},
	}

	jsonData, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", apiURL+"/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("%s错误: %v%s\n", ColorRed, err, ColorReset)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == 200 {
		body, _ := io.ReadAll(resp.Body)
		var chatResp ChatResponse
		json.Unmarshal(body, &chatResp)

		content := chatResp.Choices[0].Message.Content
		fmt.Printf("%s输出:%s\n%s\n\n", ColorCyan, ColorReset, content)

		// 解析 JSON
		var result map[string]interface{}
		if err := json.Unmarshal([]byte(content), &result); err == nil {
			fmt.Printf("%s✓ JSON 解析成功（格式保证正确）%s\n", ColorGreen, ColorReset)
			prettyJSON, _ := json.MarshalIndent(result, "", "  ")
			fmt.Printf("解析结果: %s\n\n", string(prettyJSON))
		} else {
			fmt.Printf("%s✗ JSON 解析失败: %v%s\n\n", ColorRed, err, ColorReset)
		}
	} else {
		fmt.Printf("%sAPI 错误: %d%s\n", ColorRed, resp.StatusCode, ColorReset)
	}
}

func main() {
	if err := godotenv.Load("../.env"); err != nil {
		log.Fatal("Error loading .env file")
	}

	apiURL := os.Getenv("API_BASE_URL")
	apiKey := os.Getenv("API_KEY")
	model := os.Getenv("MODEL_ID")

	fmt.Printf("%s%s\n", ColorCyan, strings.Repeat("=", 60))
	fmt.Println("结构化输出 vs 普通 JSON 对比")
	fmt.Printf("%s%s\n\n", strings.Repeat("=", 60), ColorReset)

	// 定义 JSON Schema
	schema := map[string]interface{}{
		"type": "object",
		"properties": map[string]interface{}{
			"name": map[string]interface{}{
				"type":        "string",
				"description": "姓名",
			},
			"age": map[string]interface{}{
				"type":        "integer",
				"description": "年龄",
			},
			"position": map[string]interface{}{
				"type":        "string",
				"description": "职位",
			},
			"email": map[string]interface{}{
				"type":        "string",
				"description": "邮箱",
			},
			"skills": map[string]interface{}{
				"type": "array",
				"items": map[string]interface{}{
					"type": "string",
				},
				"description": "技能列表",
			},
		},
		"required":             []string{"name", "age", "position", "email"},
		"additionalProperties": false,
	}

	prompt := "从以下文本中提取信息：张三，28岁，Python工程师，邮箱zhangsan@example.com，擅长Django和FastAPI"

	fmt.Printf("%s任务:%s %s\n\n", ColorGreen, ColorReset, prompt)
	fmt.Printf("%s%s%s\n\n", ColorCyan, strings.Repeat("-", 60), ColorReset)

	// 普通 JSON 输出
	normalJSONOutput(apiURL, apiKey, model, prompt)

	fmt.Printf("%s%s%s\n\n", ColorCyan, strings.Repeat("-", 60), ColorReset)

	// 结构化输出
	structuredOutput(apiURL, apiKey, model, prompt, schema)

	// 对比总结
	fmt.Printf("%s%s\n", ColorCyan, strings.Repeat("=", 60))
	fmt.Println("对比总结")
	fmt.Printf("%s%s\n\n", strings.Repeat("=", 60), ColorReset)

	fmt.Printf("%s普通 JSON 输出:%s\n", ColorYellow, ColorReset)
	fmt.Println("  问题:")
	fmt.Println("    - 可能包含 markdown 格式")
	fmt.Println("    - 可能有额外的说明文字")
	fmt.Println("    - 字段名可能不一致")
	fmt.Println("    - 类型可能不匹配（如年龄是字符串）")
	fmt.Println("    - 可能缺少必需字段\n")

	fmt.Printf("%s结构化输出:%s\n", ColorYellow, ColorReset)
	fmt.Println("  优势:")
	fmt.Println("    ✓ 100% 符合 JSON Schema")
	fmt.Println("    ✓ 纯 JSON，无额外格式")
	fmt.Println("    ✓ 字段名严格匹配")
	fmt.Println("    ✓ 类型严格匹配")
	fmt.Println("    ✓ 必需字段保证存在")
	fmt.Println("    ✓ 可以禁止额外字段\n")

	fmt.Printf("%s结论:%s\n", ColorGreen, ColorReset)
	fmt.Println("  结构化输出是生产环境的最佳选择")
	fmt.Println("  特别适合需要严格格式的场景\n")
}
