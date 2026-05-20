// main.go —— demo only：三个场景（简历 / 产品 / 情感分类）。
package main

import (
	"context"
	"encoding/json"
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
	cfg.HTTPClient = &http.Client{
		Transport: &http.Transport{Proxy: nil},
		Timeout:   60 * time.Second,
	}
	c := openai.NewClientWithConfig(cfg)
	model := os.Getenv("MODEL_ID")
	ctx := context.Background()

	run(ctx, c, model, "简历提取",
		"提取简历信息。",
		"张三，28岁，Python 工程师，邮箱 zs@example.com，擅长 Django、FastAPI、PostgreSQL。",
		"resume", schemaResume())

	run(ctx, c, model, "产品信息提取",
		"提取产品信息。",
		"iPhone 15 Pro 国行 9999 元，苹果出品，目前有货。",
		"product", schemaProduct())

	run(ctx, c, model, "情感分类（label 限定 positive/neutral/negative）",
		"对文本做情感分类，给出 label / confidence(0-1) / 一句话 reason。",
		"这部电影完全是浪费时间，特效粗糙，剧情拖沓。",
		"sentiment", schemaSentiment())
}

func run(ctx context.Context, c *openai.Client, model, label, system, user, name string, schema map[string]any) {
	var out map[string]any
	if err := Extract(ctx, c, model, system, user, name, schema, &out); err != nil {
		fmt.Printf("\n>>> %s\n  ERROR: %v\n", label, err)
		return
	}
	pretty, _ := json.MarshalIndent(out, "", "  ")
	fmt.Printf("\n>>> %s\n%s\n", label, string(pretty))
}

func envOr(k, fallback string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fallback
}
