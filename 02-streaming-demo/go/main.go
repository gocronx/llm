// main.go —— demo 入口。两个场景：纯文本流式、流式+function call。
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
	// 不走环境代理；本地 MLX 走代理只会失败。
	cfg.HTTPClient = &http.Client{
		Transport: &http.Transport{Proxy: nil},
		Timeout:   60 * time.Second,
	}
	client := openai.NewClientWithConfig(cfg)
	model := os.Getenv("MODEL_ID")
	ctx := context.Background()

	scenarioText(ctx, client, model)
	fmt.Println()
	scenarioTools(ctx, client, model)
}

func scenarioText(ctx context.Context, c *openai.Client, model string) {
	fmt.Println(">>> 纯文本流式：写一段 50 字内的 AI 简介")
	start := time.Now()
	var firstAt time.Duration
	n := 0
	err := StreamText(ctx, c, model, "用 50 字内介绍人工智能。", func(s string) {
		if n == 0 {
			firstAt = time.Since(start)
		}
		fmt.Print(s)
		n++
	})
	if err != nil {
		fmt.Println("\nERROR:", err)
		return
	}
	fmt.Printf("\n[首字 %.2fs / 总 %.2fs / %d chunks]\n",
		firstAt.Seconds(), time.Since(start).Seconds(), n)
}

func scenarioTools(ctx context.Context, c *openai.Client, model string) {
	fmt.Println(">>> 流式 + function call：北京天气")
	err := StreamWithTools(ctx, c, model, "北京今天天气怎么样？",
		func(ev ToolEvent) {
			fmt.Printf("[tool] %s(%s) -> %s\n", ev.Name, ev.Args, ev.Result)
		},
		func(s string) { fmt.Print(s) },
	)
	if err != nil {
		fmt.Println("\nERROR:", err)
	}
	fmt.Println()
}

func envOr(k, fallback string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fallback
}
