// client.go —— 流式输出。整文件 cp 进项目即可。
//
// StreamText: 纯文本流，回调 onDelta(content)。
// StreamWithTools: 流式 + function call。回调 onTool / onDelta。
//
// 关键点：sashabaranov/go-openai 已经把 SSE 分帧 / "data: [DONE]" 这些 HTTP
// 协议细节藏掉了；我们只关心 stream.Recv() 给出的 chunk 流。
package main

import (
	"context"
	"errors"
	"io"

	"github.com/sashabaranov/go-openai"
)

// StreamText 纯文本流式：对每个 delta content 调一次 onDelta。
func StreamText(ctx context.Context, c *openai.Client, model, userMsg string, onDelta func(string)) error {
	stream, err := c.CreateChatCompletionStream(ctx, openai.ChatCompletionRequest{
		Model:    model,
		Messages: []openai.ChatCompletionMessage{{Role: openai.ChatMessageRoleUser, Content: userMsg}},
		Stream:   true,
	})
	if err != nil {
		return err
	}
	defer stream.Close()

	for {
		resp, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		if len(resp.Choices) > 0 && resp.Choices[0].Delta.Content != "" {
			onDelta(resp.Choices[0].Delta.Content)
		}
	}
}

// ToolEvent 在 StreamWithTools 里通过 onTool 回吐：工具被调用了，参数和结果在这。
type ToolEvent struct {
	Name   string
	Args   string // 完整 JSON
	Result string
}

// StreamWithTools 流式 + function call。
//
// 第一轮 stream 里 tool_calls 按 index 分槽下发，name/arguments 都分多次。
// arguments 永远是 JSON 字符串，必须用字符串拼接而不是 dict.update —— 半截
// JSON 不是合法对象。读完整流再 unmarshal。
//
// 工具执行后回灌 assistant 决策 + tool 结果，第二轮再开 stream 输出最终文本。
func StreamWithTools(ctx context.Context, c *openai.Client, model, userMsg string,
	onTool func(ToolEvent), onDelta func(string)) error {

	messages := []openai.ChatCompletionMessage{{Role: openai.ChatMessageRoleUser, Content: userMsg}}

	first, err := c.CreateChatCompletionStream(ctx, openai.ChatCompletionRequest{
		Model: model, Messages: messages, Tools: schemas(), Stream: true,
	})
	if err != nil {
		return err
	}

	// index -> 累积的 tool_call 内容
	type slot struct {
		ID, Name, Args string
	}
	acc := map[int]*slot{}

	for {
		resp, err := first.Recv()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			first.Close()
			return err
		}
		if len(resp.Choices) == 0 {
			continue
		}
		for _, tc := range resp.Choices[0].Delta.ToolCalls {
			idx := 0
			if tc.Index != nil {
				idx = *tc.Index
			}
			s, ok := acc[idx]
			if !ok {
				s = &slot{}
				acc[idx] = s
			}
			if tc.ID != "" {
				s.ID = tc.ID
			}
			if tc.Function.Name != "" {
				s.Name = tc.Function.Name
			}
			s.Args += tc.Function.Arguments
		}
	}
	first.Close()

	if len(acc) == 0 {
		// 模型没要工具：直接重新跑一遍纯文本流。
		return StreamText(ctx, c, model, userMsg, onDelta)
	}

	// 把 assistant 决策回灌
	toolCalls := make([]openai.ToolCall, 0, len(acc))
	for _, s := range acc {
		toolCalls = append(toolCalls, openai.ToolCall{
			ID:   s.ID,
			Type: openai.ToolTypeFunction,
			Function: openai.FunctionCall{
				Name: s.Name, Arguments: s.Args,
			},
		})
	}
	messages = append(messages, openai.ChatCompletionMessage{
		Role: openai.ChatMessageRoleAssistant, ToolCalls: toolCalls,
	})

	// 执行每个工具并回灌结果
	for _, s := range acc {
		result := call(s.Name, s.Args)
		onTool(ToolEvent{Name: s.Name, Args: s.Args, Result: result})
		messages = append(messages, openai.ChatCompletionMessage{
			Role: openai.ChatMessageRoleTool, ToolCallID: s.ID, Content: result,
		})
	}

	// 第二轮流式
	second, err := c.CreateChatCompletionStream(ctx, openai.ChatCompletionRequest{
		Model: model, Messages: messages, Stream: true,
	})
	if err != nil {
		return err
	}
	defer second.Close()
	for {
		resp, err := second.Recv()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		if len(resp.Choices) > 0 && resp.Choices[0].Delta.Content != "" {
			onDelta(resp.Choices[0].Delta.Content)
		}
	}
}

