package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

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

type ChatRequest struct {
	Model      string    `json:"model"`
	Messages   []Message `json:"messages"`
	Stream     bool      `json:"stream"`
}

type ChatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

type StreamChunk struct {
	Choices []struct {
		Delta struct {
			Content string `json:"content"`
		} `json:"delta"`
	} `json:"choices"`
}

func nonStreamingRequest(apiURL, apiKey, model, prompt string) {
	fmt.Printf("%s非流式输出（等待完整响应）:%s\n\n", ColorYellow, ColorReset)

	startTime := time.Now()

	reqBody := ChatRequest{
		Model:     model,
		Messages:  []Message{{Role: "user", Content: prompt}},
		Stream:    false,
	}

	jsonData, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", apiURL+"/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("%s错误: %v%s\n", ColorRed, err, ColorReset)
		return
	}
	defer resp.Body.Close()

	waitTime := time.Since(startTime).Seconds()

	if resp.StatusCode == 200 {
		var chatResp ChatResponse
		json.NewDecoder(resp.Body).Decode(&chatResp)

		fmt.Printf("%s[等待 %.1f秒]%s\n", ColorCyan, waitTime, ColorReset)
		if len(chatResp.Choices) > 0 {
			fmt.Println(chatResp.Choices[0].Message.Content)
		}
	} else {
		fmt.Printf("%s错误: %d%s\n", ColorRed, resp.StatusCode, ColorReset)
	}
}

func streamingRequest(apiURL, apiKey, model, prompt string) {
	fmt.Printf("\n%s流式输出（逐字显示）:%s\n\n", ColorYellow, ColorReset)

	startTime := time.Now()
	var firstTokenTime *float64
	tokenCount := 0

	reqBody := ChatRequest{
		Model:     model,
		Messages:  []Message{{Role: "user", Content: prompt}},
		Stream:    true,
	}

	jsonData, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", apiURL+"/chat/completions", bytes.NewBuffer(jsonData))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("%s错误: %v%s\n", ColorRed, err, ColorReset)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == 200 {
		reader := bufio.NewReader(resp.Body)

		for {
			line, err := reader.ReadString('\n')
			if err != nil {
				if err != io.EOF {
					fmt.Printf("%s错误: %v%s\n", ColorRed, err, ColorReset)
				}
				break
			}

			line = strings.TrimSpace(line)
			if !strings.HasPrefix(line, "data: ") {
				continue
			}

			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				break
			}

			var chunk StreamChunk
			if err := json.Unmarshal([]byte(data), &chunk); err != nil {
				continue
			}

			if len(chunk.Choices) > 0 {
				content := chunk.Choices[0].Delta.Content
				if content != "" {
					if firstTokenTime == nil {
						t := time.Since(startTime).Seconds()
						firstTokenTime = &t
					}
					fmt.Print(content)
					tokenCount++
				}
			}
		}

		fmt.Println() // 换行

		totalTime := time.Since(startTime).Seconds()
		if firstTokenTime != nil {
			fmt.Printf("\n%s[首字时间: %.1f秒, 总时间: %.1f秒, Token数: %d]%s\n",
				ColorCyan, *firstTokenTime, totalTime, tokenCount, ColorReset)
		}
	} else {
		fmt.Printf("%s错误: %d%s\n", ColorRed, resp.StatusCode, ColorReset)
	}
}

func main() {
	// 加载环境变量
	if err := godotenv.Load("../.env"); err != nil {
		log.Fatal("Error loading .env file")
	}

	apiURL := os.Getenv("API_BASE_URL")
	apiKey := os.Getenv("API_KEY")
	model := os.Getenv("MODEL_ID")

	fmt.Printf("%s%s\n", ColorCyan, strings.Repeat("=", 60))
	fmt.Println("Streaming 对比演示")
	fmt.Printf("%s%s\n\n", strings.Repeat("=", 60), ColorReset)

	prompt := "请写一个关于人工智能的简短介绍，包括定义、应用和未来发展。"

	fmt.Printf("%s问题:%s %s\n\n", ColorGreen, ColorReset, prompt)
	fmt.Printf("%s%s%s\n\n", ColorCyan, strings.Repeat("-", 60), ColorReset)

	// 非流式
	nonStreamingRequest(apiURL, apiKey, model, prompt)

	fmt.Printf("\n%s%s%s\n", ColorCyan, strings.Repeat("-", 60), ColorReset)

	// 流式
	streamingRequest(apiURL, apiKey, model, prompt)

	// 总结
	fmt.Printf("\n%s%s\n", ColorCyan, strings.Repeat("=", 60))
	fmt.Println("对比总结")
	fmt.Printf("%s%s\n\n", strings.Repeat("=", 60), ColorReset)

	fmt.Printf("%s非流式输出:%s\n", ColorYellow, ColorReset)
	fmt.Println("  优点: 实现简单")
	fmt.Println("  缺点: 用户需要等待完整响应（5-10秒）")
	fmt.Println("       感觉很慢，体验差\n")

	fmt.Printf("%s流式输出:%s\n", ColorYellow, ColorReset)
	fmt.Println("  优点: 立即开始显示（0.5-1秒）")
	fmt.Println("       用户感觉很快，体验好")
	fmt.Println("  缺点: 实现稍复杂\n")

	fmt.Printf("%s结论:%s\n", ColorGreen, ColorReset)
	fmt.Println("  生产环境必须使用流式输出！")
	fmt.Println("  用户体验差异巨大。\n")
}
