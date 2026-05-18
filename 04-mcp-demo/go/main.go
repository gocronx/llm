// main.go —— demo only：让 LLM 通过 Python MCP server 创建并读回一个 todo 文件。
//
// Go 客户端拉起 ../python/server.py 作为子进程；这正是 MCP 的卖点 ——
// 工具实现在哪个语言不重要，client 只看 JSON-RPC 协议。
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
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

	workspace, _ := filepath.Abs("test_workspace")
	_ = os.MkdirAll(workspace, 0o755)

	// Python server 在上一层目录
	pyServer, _ := filepath.Abs("../python/server.py")
	mcp, err := NewMCPClient(ctx, "python3", pyServer, workspace)
	if err != nil {
		log.Fatal("mcp start:", err)
	}
	defer mcp.Close()

	bridge, err := NewBridge(mcp)
	if err != nil {
		log.Fatal("bridge:", err)
	}

	for _, q := range []string{
		"请在 todo.txt 里写三条 todo：1. 学习 MCP 2. 写 demo 3. 提 PR",
		"先列出当前目录，然后读 todo.txt 的内容回给我。",
	} {
		fmt.Println(">>>", q)
		ans, err := bridge.Chat(ctx, c, model, q, 6)
		if err != nil {
			fmt.Println("  ERROR:", err)
			continue
		}
		fmt.Println(ans)
		fmt.Println()
	}
}

func envOr(k, fb string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fb
}
