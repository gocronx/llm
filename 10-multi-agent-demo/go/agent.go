// agent.go —— 单 Agent：name + role + 一次 LLM 调用。整文件 cp 进项目即可。
package main

import (
	"context"

	"github.com/sashabaranov/go-openai"
)

type Agent struct {
	Name        string
	Role        string  // system prompt
	Client      *openai.Client
	Model       string
	Temperature float32 // 默认 0.3
}

func (a *Agent) Execute(ctx context.Context, task, extra string) (string, error) {
	user := task
	if extra != "" {
		user = task + "\n\n上游产物：\n" + extra
	}
	temp := a.Temperature
	if temp == 0 {
		temp = 0.3
	}
	resp, err := a.Client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model: a.Model,
		Messages: []openai.ChatCompletionMessage{
			{Role: openai.ChatMessageRoleSystem, Content: a.Role},
			{Role: openai.ChatMessageRoleUser, Content: user},
		},
		Temperature: temp,
		MaxTokens:   400,
	})
	if err != nil {
		return "", err
	}
	return resp.Choices[0].Message.Content, nil
}
