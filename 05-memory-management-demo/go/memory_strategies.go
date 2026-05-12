package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"unicode"

	"github.com/joho/godotenv"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Model     string    `json:"model"`
	Messages  []Message `json:"messages"`
	MaxTokens int       `json:"max_tokens"`
	Temperature float64 `json:"temperature"`
}

type ChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

var (
	apiBaseURL string
	apiKey     string
	modelID    string
)

func init() {
	godotenv.Load("../.env")
	apiBaseURL = os.Getenv("API_BASE_URL")
	apiKey = os.Getenv("API_KEY")
	modelID = os.Getenv("MODEL_ID")
}

func callLLM(messages []Message, maxTokens int) (string, error) {
	reqBody := ChatRequest{
		Model:       modelID,
		Messages:    messages,
		MaxTokens:   maxTokens,
		Temperature: 0.7,
	}

	jsonData, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", apiBaseURL+"/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var chatResp ChatResponse
	json.Unmarshal(body, &chatResp)

	if len(chatResp.Choices) > 0 {
		return chatResp.Choices[0].Message.Content, nil
	}
	return "", fmt.Errorf("no response")
}

func estimateTokens(text string) int {
	chineseChars := 0
	otherChars := 0

	for _, r := range text {
		if unicode.Is(unicode.Han, r) {
			chineseChars++
		} else {
			otherChars++
		}
	}

	return int(float64(chineseChars)/1.5 + float64(otherChars)/4)
}

func printMemoryInfo(messages []Message, strategyName string) {
	var totalText strings.Builder
	for _, m := range messages {
		totalText.WriteString(m.Content)
		totalText.WriteString(" ")
	}

	tokens := estimateTokens(totalText.String())
	fmt.Printf("\n\033[36m[%s] 记忆状态\033[0m\n", strategyName)
	fmt.Printf("  消息数量: %d\n", len(messages))
	fmt.Printf("  估算 Token: %d\n", tokens)
	fmt.Printf("  成本估算: ~$%.6f (假设 $0.01/1K tokens)\n", float64(tokens)*0.00001)
}

// ============================================================
// 策略 1: 完整记忆
// ============================================================

type FullMemoryChat struct {
	messages     []Message
	systemPrompt Message
}

func NewFullMemoryChat() *FullMemoryChat {
	return &FullMemoryChat{
		messages: []Message{},
		systemPrompt: Message{
			Role:    "system",
			Content: "你是一个友好的助手。用简短的1-2句话回答问题。",
		},
	}
}

func (c *FullMemoryChat) Chat(userInput string) (string, error) {
	c.messages = append(c.messages, Message{
		Role:    "user",
		Content: userInput,
	})

	requestMessages := append([]Message{c.systemPrompt}, c.messages...)
	response, err := callLLM(requestMessages, 150)
	if err != nil {
		return "", err
	}

	c.messages = append(c.messages, Message{
		Role:    "assistant",
		Content: response,
	})

	return response, nil
}

func (c *FullMemoryChat) GetMemoryInfo() {
	allMessages := append([]Message{c.systemPrompt}, c.messages...)
	printMemoryInfo(allMessages, "完整记忆")
}

// ============================================================
// 策略 2: 滑动窗口
// ============================================================

type SlidingWindowChat struct {
	messages     []Message
	windowSize   int
	systemPrompt Message
}

func NewSlidingWindowChat(windowSize int) *SlidingWindowChat {
	return &SlidingWindowChat{
		messages:   []Message{},
		windowSize: windowSize,
		systemPrompt: Message{
			Role:    "system",
			Content: "你是一个友好的助手。用简短的1-2句话回答问题。",
		},
	}
}

func (c *SlidingWindowChat) Chat(userInput string) (string, error) {
	c.messages = append(c.messages, Message{
		Role:    "user",
		Content: userInput,
	})

	if len(c.messages) > c.windowSize {
		c.messages = c.messages[len(c.messages)-c.windowSize:]
	}

	requestMessages := append([]Message{c.systemPrompt}, c.messages...)
	response, err := callLLM(requestMessages, 150)
	if err != nil {
		return "", err
	}

	c.messages = append(c.messages, Message{
		Role:    "assistant",
		Content: response,
	})

	if len(c.messages) > c.windowSize {
		c.messages = c.messages[len(c.messages)-c.windowSize:]
	}

	return response, nil
}

func (c *SlidingWindowChat) GetMemoryInfo() {
	allMessages := append([]Message{c.systemPrompt}, c.messages...)
	printMemoryInfo(allMessages, "滑动窗口")
	fmt.Printf("  窗口大小: %d\n", c.windowSize)
}

// ============================================================
// 策略 3: Token 限制
// ============================================================

type TokenLimitedChat struct {
	messages     []Message
	maxTokens    int
	systemPrompt Message
}

func NewTokenLimitedChat(maxTokens int) *TokenLimitedChat {
	return &TokenLimitedChat{
		messages:  []Message{},
		maxTokens: maxTokens,
		systemPrompt: Message{
			Role:    "system",
			Content: "你是一个友好的助手。用简短的1-2句话回答问题。",
		},
	}
}

func (c *TokenLimitedChat) Chat(userInput string) (string, error) {
	c.messages = append(c.messages, Message{
		Role:    "user",
		Content: userInput,
	})

	c.trimByTokens()

	requestMessages := append([]Message{c.systemPrompt}, c.messages...)
	response, err := callLLM(requestMessages, 150)
	if err != nil {
		return "", err
	}

	c.messages = append(c.messages, Message{
		Role:    "assistant",
		Content: response,
	})

	c.trimByTokens()

	return response, nil
}

func (c *TokenLimitedChat) trimByTokens() {
	for len(c.messages) > 2 {
		var totalText strings.Builder
		totalText.WriteString(c.systemPrompt.Content)
		totalText.WriteString(" ")
		for _, m := range c.messages {
			totalText.WriteString(m.Content)
			totalText.WriteString(" ")
		}

		tokens := estimateTokens(totalText.String())
		if tokens <= c.maxTokens {
			break
		}

		c.messages = c.messages[1:]
	}
}

func (c *TokenLimitedChat) GetMemoryInfo() {
	allMessages := append([]Message{c.systemPrompt}, c.messages...)
	printMemoryInfo(allMessages, "Token 限制")
	fmt.Printf("  Token 限制: %d\n", c.maxTokens)
}

// ============================================================
// 主演示
// ============================================================

func demoStrategy(chat interface{}, strategyName string, conversations []string) {
	fmt.Printf("\n\033[36m%s\n%s\n%s\033[0m\n\n", strings.Repeat("=", 60), strategyName, strings.Repeat("=", 60))

	for i, userInput := range conversations {
		fmt.Printf("\n\033[32m[轮次 %d] 用户:\033[0m %s\n", i+1, userInput)

		var response string
		var err error

		switch c := chat.(type) {
		case *FullMemoryChat:
			response, err = c.Chat(userInput)
			if err == nil {
				fmt.Printf("\033[34m助手:\033[0m %s\n", truncate(response, 150))
				c.GetMemoryInfo()
			}
		case *SlidingWindowChat:
			response, err = c.Chat(userInput)
			if err == nil {
				fmt.Printf("\033[34m助手:\033[0m %s\n", truncate(response, 150))
				c.GetMemoryInfo()
			}
		case *TokenLimitedChat:
			response, err = c.Chat(userInput)
			if err == nil {
				fmt.Printf("\033[34m助手:\033[0m %s\n", truncate(response, 150))
				c.GetMemoryInfo()
			}
		}

		if err != nil {
			fmt.Printf("错误: %v\n", err)
		}
	}
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

func main() {
	fmt.Printf("\033[36m%s\n对话记忆管理策略演示\n%s\033[0m\n\n", strings.Repeat("=", 60), strings.Repeat("=", 60))

	conversations := []string{
		"你好，我叫张三",
		"我今年 25 岁",
		"我喜欢编程",
		"我刚才说我叫什么名字？",
		"我多大了？",
		"我有什么爱好？",
	}

	fmt.Println("\033[33m测试对话序列:\033[0m")
	for i, conv := range conversations {
		fmt.Printf("  %d. %s\n", i+1, conv)
	}

	// 策略 1: 完整记忆
	demoStrategy(NewFullMemoryChat(), "策略 1: 完整记忆（Full Memory）", conversations)

	// 策略 2: 滑动窗口
	demoStrategy(NewSlidingWindowChat(4), "策略 2: 滑动窗口（Sliding Window, 窗口=4）", conversations)

	// 策略 3: Token 限制
	demoStrategy(NewTokenLimitedChat(300), "策略 3: Token 限制（Token-Limited, 限制=300）", conversations)

	// 总结
	fmt.Printf("\n\033[36m%s\n策略对比总结\n%s\033[0m\n\n", strings.Repeat("=", 60), strings.Repeat("=", 60))

	fmt.Println("\033[33m1. 完整记忆\033[0m")
	fmt.Println("  ✅ 优点: 记住所有信息，上下文完整")
	fmt.Println("  ❌ 缺点: Token 消耗大，成本高")
	fmt.Println("  📌 适用: 短对话、重要对话\n")

	fmt.Println("\033[33m2. 滑动窗口\033[0m")
	fmt.Println("  ✅ 优点: Token 可控，实现简单")
	fmt.Println("  ❌ 缺点: 会忘记早期信息")
	fmt.Println("  📌 适用: 一般对话、成本敏感场景\n")

	fmt.Println("\033[33m3. Token 限制\033[0m")
	fmt.Println("  ✅ 优点: 精确控制成本")
	fmt.Println("  ❌ 缺点: 可能在对话中途突然'失忆'")
	fmt.Println("  📌 适用: 严格成本控制场景\n")

	fmt.Println("\033[32m建议:\033[0m")
	fmt.Println("  - 短对话（<10 轮）：完整记忆")
	fmt.Println("  - 一般对话（10-50 轮）：滑动窗口")
	fmt.Println("  - 成本敏感：Token 限制\n")
}
