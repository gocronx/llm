// client.go —— MCP ↔ OpenAI 桥接。整文件 cp 进项目即可。
//
// Bridge 把 MCP 的 tools/list 翻译成 OpenAI 的 tools 字段，把 OpenAI 的
// tool_calls 翻译回 MCP 的 tools/call。LLM 不需要知道 MCP 的存在。
package main

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/sashabaranov/go-openai"
)

type Bridge struct {
	mcp       *MCPClient
	openaiSch []openai.Tool
}

func NewBridge(mcp *MCPClient) (*Bridge, error) {
	tools, err := mcp.ListTools()
	if err != nil {
		return nil, err
	}
	openaiSch := make([]openai.Tool, 0, len(tools))
	for _, t := range tools {
		schemaBytes, _ := json.Marshal(t.InputSchema)
		openaiSch = append(openaiSch, openai.Tool{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        t.Name,
				Description: t.Description,
				Parameters:  json.RawMessage(schemaBytes),
			},
		})
	}
	return &Bridge{mcp: mcp, openaiSch: openaiSch}, nil
}

// Chat 多轮 LLM ↔ tools 循环，直到 LLM 不再 call tool。
func (b *Bridge) Chat(ctx context.Context, c *openai.Client, model, userMsg string, maxRounds int) (string, error) {
	messages := []openai.ChatCompletionMessage{
		{Role: openai.ChatMessageRoleUser, Content: userMsg},
	}
	for i := 0; i < maxRounds; i++ {
		resp, err := c.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
			Model: model, Messages: messages, Tools: b.openaiSch,
		})
		if err != nil {
			return "", err
		}
		msg := resp.Choices[0].Message
		if len(msg.ToolCalls) == 0 {
			return msg.Content, nil
		}
		messages = append(messages, msg)
		for _, tc := range msg.ToolCalls {
			var args map[string]any
			if err := json.Unmarshal([]byte(tc.Function.Arguments), &args); err != nil {
				args = map[string]any{}
			}
			out, err := b.mcp.CallTool(tc.Function.Name, args)
			if err != nil {
				out = fmt.Sprintf(`{"error": %q}`, err.Error())
			}
			messages = append(messages, openai.ChatCompletionMessage{
				Role: openai.ChatMessageRoleTool, ToolCallID: tc.ID, Content: out,
			})
		}
	}
	return "(max rounds reached)", nil
}
