// chat.go —— Memory + OpenAI 客户端 = 一个会话。整文件 cp 进项目即可。
package main

import (
	"context"

	"github.com/sashabaranov/go-openai"
)

type Chat struct {
	client *openai.Client
	model  string
	mem    Memory
}

func NewChat(c *openai.Client, model string, mem Memory) *Chat {
	return &Chat{client: c, model: model, mem: mem}
}

func (ch *Chat) Ask(ctx context.Context, userMsg string) (string, error) {
	ch.mem.Append(openai.ChatMessageRoleUser, userMsg)
	resp, err := ch.client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model:       ch.model,
		Messages:    ch.mem.Messages(),
		MaxTokens:   200,
		Temperature: 0.3,
	})
	if err != nil {
		return "", err
	}
	answer := resp.Choices[0].Message.Content
	ch.mem.Append(openai.ChatMessageRoleAssistant, answer)
	return answer, nil
}

// MakeSummarizer 注入给 NewSummary 用：把 msgs 压成一段事实。
func MakeSummarizer(ctx context.Context, c *openai.Client, model string) SummarizeFn {
	return func(msgs []openai.ChatCompletionMessage) string {
		joined := ""
		for _, m := range msgs {
			joined += m.Role + ": " + m.Content + "\n"
		}
		resp, err := c.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
			Model: model,
			Messages: []openai.ChatCompletionMessage{
				{Role: openai.ChatMessageRoleSystem, Content: "提取对话中的关键事实，按 - 列表，每条一行。"},
				{Role: openai.ChatMessageRoleUser, Content: joined},
			},
			MaxTokens:   150,
			Temperature: 0,
		})
		if err != nil {
			return "(summarize failed: " + err.Error() + ")"
		}
		return resp.Choices[0].Message.Content
	}
}
