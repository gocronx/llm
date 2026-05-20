// main.go —— demo only：同一组对话喂给四种 memory。
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

const SYSTEM = "你是友好的助手，用一句话简短回答。"

var DIALOG = []string{
	"你好，我叫张三",
	"我今年 25 岁",
	"我喜欢编程",
	"我刚才说我叫什么？",
	"我多大？",
	"我有什么爱好？",
}

func main() {
	if err := godotenv.Load("../.env"); err != nil {
		log.Println("warning: .env not loaded:", err)
	}

	cfg := openai.DefaultConfig(envOr("API_KEY", "not-needed"))
	cfg.BaseURL = os.Getenv("API_BASE_URL")
	cfg.HTTPClient = &http.Client{
		Transport: &http.Transport{Proxy: nil},
		Timeout:   60 * time.Second,
	}
	c := openai.NewClientWithConfig(cfg)
	model := os.Getenv("MODEL_ID")
	ctx := context.Background()

	run(ctx, c, model, "Full（全留）", NewFull(SYSTEM))
	run(ctx, c, model, "Window(k=4)", NewWindow(SYSTEM, 4))
	run(ctx, c, model, "Tokens(max=200)", NewTokens(SYSTEM, 200))
	run(ctx, c, model, "Summary(k=4)", NewSummary(SYSTEM, 4, MakeSummarizer(ctx, c, model)))
}

func run(ctx context.Context, c *openai.Client, model, label string, mem Memory) {
	fmt.Printf("\n=== %s ===\n", label)
	chat := NewChat(c, model, mem)
	for _, q := range DIALOG {
		ans, err := chat.Ask(ctx, q)
		if err != nil {
			fmt.Println("  ERROR:", err)
			continue
		}
		toks := 0
		for _, m := range mem.Messages() {
			toks += EstimateTokens(m.Content)
		}
		fmt.Printf("  Q: %s\n  A: %s  [ctx≈%dt, %dmsg]\n", q, trim(ans), toks, len(mem.Messages()))
	}
}

func trim(s string) string {
	if len(s) > 100 {
		return s[:100] + "..."
	}
	return s
}

func envOr(k, fb string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fb
}
