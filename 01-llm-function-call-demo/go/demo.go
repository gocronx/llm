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

func callLLM(messages []Message, functions []FunctionDefinition) (*ChatResponse, error) {
	// 加载配置
	godotenv.Load("../.env")
	apiBaseURL := os.Getenv("API_BASE_URL")
	apiKey := os.Getenv("API_KEY")
	modelID := os.Getenv("MODEL_ID")

	var tools []Tool
	if functions != nil {
		for _, fn := range functions {
			tools = append(tools, Tool{
				Type:     "function",
				Function: fn,
			})
		}
	}

	request := ChatRequest{
		Model:     modelID,
		Messages:  messages,
		Tools:     tools,
		MaxTokens: 1000,
	}

	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", apiBaseURL+"/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("API error: %s", string(body))
	}

	var response ChatResponse
	err = json.Unmarshal(body, &response)
	if err != nil {
		return nil, err
	}

	return &response, nil
}

func runFunctionCall(userMessage string) {
	fmt.Println(strings.Repeat("=", 60))
	fmt.Printf("用户: %s\n", userMessage)
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println()

	messages := []Message{
		{Role: "user", Content: userMessage},
	}

	// 第一次调用：让 LLM 决定是否调用函数
	fmt.Println("→ 发送请求到 LLM...")
	response, err := callLLM(messages, FunctionDefinitions)
	if err != nil {
		fmt.Printf("✗ API 调用失败: %v\n\n", err)
		return
	}

	message := response.Choices[0].Message

	if len(message.ToolCalls) > 0 {
		// LLM 决定调用函数
		toolCall := message.ToolCalls[0]
		funcName := toolCall.Function.Name
		var funcArgs map[string]interface{}
		json.Unmarshal([]byte(toolCall.Function.Arguments), &funcArgs)

		argsJSON, _ := json.Marshal(funcArgs)
		fmt.Printf("✓ LLM 调用函数: %s\n", funcName)
		fmt.Printf("  参数: %s\n\n", string(argsJSON))

		// 执行函数
		fmt.Println("→ 执行函数...")
		result := ExecuteFunction(funcName, funcArgs)
		fmt.Printf("✓ 函数返回: %s\n\n", result)

		// 第二次调用：生成最终回答
		messages = append(messages, message)
		messages = append(messages, Message{
			Role:       "tool",
			ToolCallID: toolCall.ID,
			Name:       funcName,
			Content:    result,
		})

		fmt.Println("→ 生成最终回答...")
		finalResponse, err := callLLM(messages, nil)
		if err != nil {
			fmt.Printf("✗ API 调用失败: %v\n\n", err)
			return
		}

		answer := finalResponse.Choices[0].Message.Content
		fmt.Printf("✓ 最终回答:\n%s\n\n", answer)
	} else {
		// 直接回答
		content := message.Content
		fmt.Printf("✓ LLM 直接回答:\n%s\n\n", content)
	}
}

func main() {
	fmt.Println()
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println("Function Call Demo (Go)")
	fmt.Println(strings.Repeat("=", 60))

	runFunctionCall("北京今天天气怎么样？")
	runFunctionCall("156 除以 12 等于多少？")
	runFunctionCall("搜索价格在500元以上的产品")
}
