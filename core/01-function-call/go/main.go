// main.go —— demo 入口。
// 默认跑三个 demo 场景；`go run . verify` 验证 LLM 在三类问题上调对了工具。
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/joho/godotenv"
	"github.com/sashabaranov/go-openai"
)

func main() {
	if err := godotenv.Load("../.env"); err != nil {
		log.Println("warning: .env not loaded:", err)
	}

	cfg := openai.DefaultConfig(envOr("API_KEY", "not-needed"))
	cfg.BaseURL = os.Getenv("API_BASE_URL")
	// 显式给一个不走环境代理的 http.Client。Go 默认 http.ProxyFromEnvironment
	// 会读 HTTP_PROXY；本地 MLX 场景下走代理只会失败。
	cfg.HTTPClient = &http.Client{
		Transport: &http.Transport{Proxy: nil},
		Timeout:   60 * time.Second,
	}
	client := openai.NewClientWithConfig(cfg)
	model := os.Getenv("MODEL_ID")
	ctx := context.Background()

	if len(os.Args) > 1 && os.Args[1] == "verify" {
		verify(ctx, client, model)
		return
	}
	demo(ctx, client, model)
}

func demo(ctx context.Context, client *openai.Client, model string) {
	for _, q := range []string{
		"北京今天天气怎么样？",
		"156 除以 12 等于多少？",
		"搜索价格在 500 元以上的产品",
	} {
		fmt.Println(">>>", q)
		ans, err := Run(ctx, client, model, q)
		if err != nil {
			fmt.Println("  ERROR:", err)
			continue
		}
		fmt.Println(ans)
		fmt.Println()
	}
}

func verify(ctx context.Context, client *openai.Client, model string) {
	cases := []struct{ q, expected string }{
		{"北京天气怎么样？", "get_weather"},
		{"156 除以 12", "calculate"},
		{"搜索笔记本相关的产品", "search_products"},
	}
	passed := 0
	for _, c := range cases {
		resp, err := client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
			Model:    model,
			Messages: []openai.ChatCompletionMessage{{Role: openai.ChatMessageRoleUser, Content: c.q}},
			Tools:    schemas(),
		})
		got := "(no tool call)"
		switch {
		case err != nil:
			got = "ERROR: " + err.Error()
		case len(resp.Choices[0].Message.ToolCalls) > 0:
			got = resp.Choices[0].Message.ToolCalls[0].Function.Name
		}
		ok := got == c.expected
		mark := "✗"
		if ok {
			mark = "✓"
			passed++
		}
		fmt.Printf("%s %-30s expected=%-18s got=%s\n", mark, c.q, c.expected, got)
	}
	fmt.Printf("\n%d/%d passed\n", passed, len(cases))
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
