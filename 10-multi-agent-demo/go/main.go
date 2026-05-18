// main.go —— demo only：writer → reviewer → editor 顺序；3 写手并行。
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
	cfg.HTTPClient = &http.Client{
		Transport: &http.Transport{Proxy: nil},
		Timeout:   60 * time.Second,
	}
	c := openai.NewClientWithConfig(cfg)
	model := os.Getenv("MODEL_ID")
	ctx := context.Background()

	agents := map[string]*Agent{
		"writer":   {Name: "writer", Client: c, Model: model, Role: "你是技术博客写手。给出 200 字内的文章主体，不要标题。"},
		"reviewer": {Name: "reviewer", Client: c, Model: model, Role: "你是技术评审员。读上游产物，按 - 列表给 3 条具体改进建议，每条不超过 20 字。"},
		"editor":   {Name: "editor", Client: c, Model: model, Role: "你是编辑。综合 writer 的初稿和 reviewer 的建议，输出最终成稿。禁止添加解释，直接输出修改后的文章。"},
	}

	// ---- 顺序 ----
	fmt.Println("\n=== 顺序工作流：writer → reviewer → editor ===")
	wf := []Step{
		{ID: "draft", Agent: "writer", Task: "写一段关于 Go 并发编程的简短科普"},
		{ID: "review", Agent: "reviewer", Task: "评审上面的初稿", DependsOn: []string{"draft"}},
		{ID: "final", Agent: "editor", Task: "按 reviewer 建议修改 draft，输出终稿", DependsOn: []string{"draft", "review"}},
	}
	results, err := RunSequential(ctx, agents, wf)
	if err != nil {
		log.Println("sequential error:", err)
	}
	for _, id := range []string{"draft", "review", "final"} {
		fmt.Printf("\n--- %s ---\n%s\n", id, results[id])
	}

	// ---- 并行 ----
	fmt.Println("\n=== 并行工作流：3 个 writer 各写一段 ===")
	steps := []Step{
		{ID: "py", Agent: "writer", Task: "写一句 Python 的优点"},
		{ID: "rust", Agent: "writer", Task: "写一句 Rust 的优点"},
		{ID: "go", Agent: "writer", Task: "写一句 Go 的优点"},
	}
	r := RunParallel(ctx, agents, steps)
	for _, id := range []string{"py", "rust", "go"} {
		fmt.Printf("  [%s] %s\n", id, r[id])
	}
}

func envOr(k, fb string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fb
}
