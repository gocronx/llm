package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

// TestMCPHandshake verifies the Go client can spawn the Python MCP server,
// complete the initialize/notifications/initialized handshake, and list tools.
// Skipped if Python or the server is unavailable.
func TestMCPHandshake(t *testing.T) {
	pyServer, err := filepath.Abs("../python/server.py")
	if err != nil || !fileExists(pyServer) {
		t.Skipf("python server.py not found: %v", err)
	}
	wd, _ := os.MkdirTemp("", "mcp-test-")
	defer os.RemoveAll(wd)

	ctx := context.Background()
	mcp, err := NewMCPClient(ctx, "python3", pyServer, wd)
	if err != nil {
		t.Fatalf("spawn: %v", err)
	}
	defer mcp.Close()

	tools, err := mcp.ListTools()
	if err != nil {
		t.Fatalf("list_tools: %v", err)
	}
	want := map[string]bool{"read_file": false, "write_file": false, "list_directory": false}
	for _, tool := range tools {
		want[tool.Name] = true
	}
	for name, found := range want {
		if !found {
			t.Errorf("missing tool: %s", name)
		}
	}

	// One round-trip call to confirm tools/call works
	out, err := mcp.CallTool("write_file", map[string]any{
		"path": "smoke.txt", "content": "from go",
	})
	if err != nil {
		t.Fatalf("call write_file: %v", err)
	}
	if out == "" {
		t.Error("write_file returned empty")
	}
	out, err = mcp.CallTool("read_file", map[string]any{"path": "smoke.txt"})
	if err != nil || out != "from go" {
		t.Errorf("read_file mismatch: %q err=%v", out, err)
	}
}

func fileExists(p string) bool {
	_, err := os.Stat(p)
	return err == nil
}
