// mcp.go —— 极简 MCP-stdio 客户端。整文件 cp 进项目即可。
//
// MCP over stdio = JSON-RPC 2.0 over NDJSON：
//   - 每条消息一行 JSON
//   - 请求带 `id`，server 用同 `id` 回响应
//   - 通知（notifications/*）没 `id`，server 不回
//
// 三步握手：initialize -> notifications/initialized -> tools/list 就能用了。
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"sync"
	"sync/atomic"
)

type MCPTool struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"inputSchema"`
}

type MCPClient struct {
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	scanner *bufio.Scanner

	nextID  atomic.Int64
	mu      sync.Mutex
	pending map[int64]chan json.RawMessage
}

// NewMCPClient 拉起 server 子进程并完成握手。Close() 一定要调，否则子进程泄漏。
func NewMCPClient(ctx context.Context, command string, args ...string) (*MCPClient, error) {
	cmd := exec.CommandContext(ctx, command, args...)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		return nil, err
	}

	scanner := bufio.NewScanner(stdout)
	// MCP 单条消息可能很长（list_tools 把 schema 全塞进来），把缓冲打满
	scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)

	c := &MCPClient{
		cmd: cmd, stdin: stdin, scanner: scanner,
		pending: map[int64]chan json.RawMessage{},
	}
	go c.readLoop()

	// 握手
	if _, err := c.call("initialize", map[string]any{
		"protocolVersion": "2024-11-05",
		"capabilities":    map[string]any{},
		"clientInfo":      map[string]any{"name": "go-mcp-client", "version": "0.1"},
	}); err != nil {
		c.Close()
		return nil, err
	}
	if err := c.notify("notifications/initialized", nil); err != nil {
		c.Close()
		return nil, err
	}
	return c, nil
}

func (c *MCPClient) Close() error {
	_ = c.stdin.Close()
	return c.cmd.Wait()
}

// ListTools 拿到所有可调用工具。
func (c *MCPClient) ListTools() ([]MCPTool, error) {
	raw, err := c.call("tools/list", nil)
	if err != nil {
		return nil, err
	}
	var resp struct {
		Tools []MCPTool `json:"tools"`
	}
	if err := json.Unmarshal(raw, &resp); err != nil {
		return nil, err
	}
	return resp.Tools, nil
}

// CallTool 跑一次 tools/call，把结果文本拼起来返回。
func (c *MCPClient) CallTool(name string, args map[string]any) (string, error) {
	raw, err := c.call("tools/call", map[string]any{"name": name, "arguments": args})
	if err != nil {
		return "", err
	}
	var resp struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
		IsError bool `json:"isError"`
	}
	if err := json.Unmarshal(raw, &resp); err != nil {
		return "", err
	}
	out := ""
	for _, c := range resp.Content {
		if c.Type == "text" {
			out += c.Text
		}
	}
	if resp.IsError {
		return out, fmt.Errorf("tool error: %s", out)
	}
	return out, nil
}

// ---- 内部 ----

type rpcResp struct {
	ID     int64           `json:"id"`
	Result json.RawMessage `json:"result"`
	Error  *struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

func (c *MCPClient) readLoop() {
	for c.scanner.Scan() {
		var r rpcResp
		if err := json.Unmarshal(c.scanner.Bytes(), &r); err != nil {
			continue
		}
		if r.ID == 0 {
			// 通知，没人在等，忽略
			continue
		}
		c.mu.Lock()
		ch, ok := c.pending[r.ID]
		delete(c.pending, r.ID)
		c.mu.Unlock()
		if !ok {
			continue
		}
		if r.Error != nil {
			ch <- json.RawMessage(fmt.Sprintf(`{"__rpc_error__":%q}`, r.Error.Message))
		} else {
			ch <- r.Result
		}
		close(ch)
	}
}

func (c *MCPClient) call(method string, params any) (json.RawMessage, error) {
	id := c.nextID.Add(1)
	ch := make(chan json.RawMessage, 1)
	c.mu.Lock()
	c.pending[id] = ch
	c.mu.Unlock()

	msg := map[string]any{"jsonrpc": "2.0", "id": id, "method": method}
	if params != nil {
		msg["params"] = params
	}
	b, _ := json.Marshal(msg)
	if _, err := c.stdin.Write(append(b, '\n')); err != nil {
		return nil, err
	}
	raw := <-ch
	// 简单错误透传
	var errCheck struct {
		Msg string `json:"__rpc_error__"`
	}
	if json.Unmarshal(raw, &errCheck) == nil && errCheck.Msg != "" {
		return nil, fmt.Errorf("%s", errCheck.Msg)
	}
	return raw, nil
}

func (c *MCPClient) notify(method string, params any) error {
	msg := map[string]any{"jsonrpc": "2.0", "method": method}
	if params != nil {
		msg["params"] = params
	}
	b, _ := json.Marshal(msg)
	_, err := c.stdin.Write(append(b, '\n'))
	return err
}
