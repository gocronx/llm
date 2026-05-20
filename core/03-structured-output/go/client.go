// client.go —— 结构化输出。整文件 cp 进项目即可。
//
// 用 sashabaranov/go-openai 的 ChatCompletionResponseFormatJSONSchema：
// strict=true 让 OpenAI 在解码时按 schema 约束，content 一定是合法 JSON。
package main

import (
	"context"
	"encoding/json"

	"github.com/sashabaranov/go-openai"
)

// Extract 让 LLM 按 schema 返回 JSON，自动 unmarshal 进 out。
// out 必须是指针（指向 map 或具体 struct）。
func Extract(ctx context.Context, c *openai.Client, model, system, user, name string,
	schema map[string]any, out any) error {

	schemaBytes, err := json.Marshal(schema)
	if err != nil {
		return err
	}

	resp, err := c.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model: model,
		Messages: []openai.ChatCompletionMessage{
			{Role: openai.ChatMessageRoleSystem, Content: system},
			{Role: openai.ChatMessageRoleUser, Content: user},
		},
		ResponseFormat: &openai.ChatCompletionResponseFormat{
			Type: openai.ChatCompletionResponseFormatTypeJSONSchema,
			JSONSchema: &openai.ChatCompletionResponseFormatJSONSchema{
				Name:   name,
				Schema: json.RawMessage(schemaBytes),
				Strict: true,
			},
		},
	})
	if err != nil {
		return err
	}
	// strict 模式下 Content 必是合法 JSON；解析失败说明 schema 自己不合法
	// 或者本地模型没真支持 strict，需要去修不是 swallow
	return json.Unmarshal([]byte(resp.Choices[0].Message.Content), out)
}
