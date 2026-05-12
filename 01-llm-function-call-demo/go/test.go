package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/joho/godotenv"
)

func testFunctionCall() {
	// 加载配置
	godotenv.Load("../.env")
	apiBaseURL := os.Getenv("API_BASE_URL")
	apiKey := os.Getenv("API_KEY")
	modelID := os.Getenv("MODEL_ID")

	fmt.Println()
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println("Function Call 测试 (Go)")
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println()

	testCases := []struct {
		name     string
		question string
		expected string
	}{
		{"天气查询", "北京天气怎么样？", "get_weather"},
		{"数学计算", "156 除以 12", "calculate"},
		{"数据库搜索", "帮我在数据库中搜索笔记本相关的产品", "search_database"},
	}

	results := []bool{}

	for _, tc := range testCases {
		fmt.Printf("测试: %s\n", tc.name)
		fmt.Printf("问题: %s\n", tc.question)

		// 构建请求
		var tools []Tool
		for _, fn := range FunctionDefinitions {
			tools = append(tools, Tool{
				Type:     "function",
				Function: fn,
			})
		}

		request := ChatRequest{
			Model: modelID,
			Messages: []Message{
				{Role: "user", Content: tc.question},
			},
			Tools:     tools,
			MaxTokens: 500,
		}

		jsonData, err := json.Marshal(request)
		if err != nil {
			fmt.Printf("结果: ✗ JSON 错误: %v\n\n", err)
			results = append(results, false)
			continue
		}

		req, err := http.NewRequest("POST", apiBaseURL+"/chat/completions", bytes.NewBuffer(jsonData))
		if err != nil {
			fmt.Printf("结果: ✗ 请求错误: %v\n\n", err)
			results = append(results, false)
			continue
		}

		req.Header.Set("Authorization", "Bearer "+apiKey)
		req.Header.Set("Content-Type", "application/json")

		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			fmt.Printf("结果: ✗ API 错误: %v\n\n", err)
			results = append(results, false)
			continue
		}

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != 200 {
			fmt.Printf("结果: ✗ API 错误: %s\n\n", string(body))
			results = append(results, false)
			continue
		}

		var response ChatResponse
		err = json.Unmarshal(body, &response)
		if err != nil {
			fmt.Printf("结果: ✗ 解析错误: %v\n\n", err)
			results = append(results, false)
			continue
		}

		toolCalls := response.Choices[0].Message.ToolCalls
		if len(toolCalls) > 0 {
			funcName := toolCalls[0].Function.Name
			success := funcName == tc.expected
			if success {
				fmt.Printf("结果: ✓ 调用了 %s\n\n", funcName)
			} else {
				fmt.Printf("结果: ✗ 调用了 %s (期望 %s)\n\n", funcName, tc.expected)
			}
			results = append(results, success)
		} else {
			fmt.Println("结果: ✗ 未调用函数\n")
			results = append(results, false)
		}
	}

	passed := 0
	for _, r := range results {
		if r {
			passed++
		}
	}

	fmt.Println(strings.Repeat("=", 60))
	fmt.Printf("测试结果: %d/%d 通过\n", passed, len(results))
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println()
}

func main() {
	testFunctionCall()
}
