// client.go —— Function Call 的两轮交互。整文件 cp 进项目即可。
//
// 第一轮：把 user message + tools 发给 LLM，LLM 返回 tool_calls 决策。
// 应用层：照决策执行工具，把结果作为 role=tool 消息回灌。
// 第二轮：LLM 看着工具结果生成最终自然语言回答。
package main

import (
	"context"

	"github.com/sashabaranov/go-openai"
)

// Run 一次 function-call 往返，返回 LLM 的最终回答。
func Run(ctx context.Context, client *openai.Client, model, userMsg string) (string, error) {
	messages := []openai.ChatCompletionMessage{
		{Role: openai.ChatMessageRoleUser, Content: userMsg},
	}

	first, err := client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model:    model,
		Messages: messages,
		Tools:    schemas(),
	})
	if err != nil {
		return "", err
	}

	msg := first.Choices[0].Message
	if len(msg.ToolCalls) == 0 {
		return msg.Content, nil
	}

	// assistant 的 tool_calls 决策必须回灌，否则第二轮 LLM 看不到自己刚才说了啥
	messages = append(messages, msg)

	// LLM 一次可能调多个工具，全跑完再回 LLM
	for _, tc := range msg.ToolCalls {
		messages = append(messages, openai.ChatCompletionMessage{
			Role:       openai.ChatMessageRoleTool,
			ToolCallID: tc.ID,
			Content:    call(tc.Function.Name, tc.Function.Arguments),
		})
	}

	second, err := client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model:    model,
		Messages: messages,
	})
	if err != nil {
		return "", err
	}
	return second.Choices[0].Message.Content, nil
}
