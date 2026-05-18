// memory.go —— 四种对话记忆策略。整文件 cp 进项目即可。
//
// Full     —— 不裁
// Window   —— 只留最近 k 条
// Tokens   —— 估算 token 超 N 就从头扔
// Summary  —— 攒 k 条 → 注入函数压成一段事实
//
// 接口：Append(role, content) / Messages() []ChatCompletionMessage
package main

import (
	"github.com/sashabaranov/go-openai"
)

type Memory interface {
	Append(role, content string)
	Messages() []openai.ChatCompletionMessage
}

// EstimateTokens 糙估：中文 1.5 字符/token，其它 4 字符/token。
// 生产换 tiktoken / cl100k_base 真 tokenizer。
func EstimateTokens(s string) int {
	cn := 0
	for _, r := range s {
		if r >= 0x4e00 && r <= 0x9fff {
			cn++
		}
	}
	other := len([]rune(s)) - cn
	return cn*2/3 + other/4
}

type base struct {
	system string
	msgs   []openai.ChatCompletionMessage
}

func (b *base) sys() openai.ChatCompletionMessage {
	return openai.ChatCompletionMessage{Role: openai.ChatMessageRoleSystem, Content: b.system}
}

// ---- Full ----

type Full struct{ base }

func NewFull(system string) *Full                  { return &Full{base{system: system}} }
func (m *Full) Append(role, content string)        { m.msgs = append(m.msgs, openai.ChatCompletionMessage{Role: role, Content: content}) }
func (m *Full) Messages() []openai.ChatCompletionMessage {
	return append([]openai.ChatCompletionMessage{m.sys()}, m.msgs...)
}

// ---- Window ----

type Window struct {
	base
	k int
}

func NewWindow(system string, k int) *Window { return &Window{base{system: system}, k} }

func (m *Window) Append(role, content string) {
	m.msgs = append(m.msgs, openai.ChatCompletionMessage{Role: role, Content: content})
	if len(m.msgs) > m.k {
		m.msgs = m.msgs[len(m.msgs)-m.k:]
	}
}

func (m *Window) Messages() []openai.ChatCompletionMessage {
	return append([]openai.ChatCompletionMessage{m.sys()}, m.msgs...)
}

// ---- Tokens ----

type Tokens struct {
	base
	maxTokens int
}

func NewTokens(system string, maxTokens int) *Tokens {
	return &Tokens{base{system: system}, maxTokens}
}

func (m *Tokens) Append(role, content string) {
	m.msgs = append(m.msgs, openai.ChatCompletionMessage{Role: role, Content: content})
	total := func() int {
		t := EstimateTokens(m.system)
		for _, x := range m.msgs {
			t += EstimateTokens(x.Content)
		}
		return t
	}
	// 至少留 1 条，否则模型完全失忆
	for len(m.msgs) > 1 && total() > m.maxTokens {
		m.msgs = m.msgs[1:]
	}
}

func (m *Tokens) Messages() []openai.ChatCompletionMessage {
	return append([]openai.ChatCompletionMessage{m.sys()}, m.msgs...)
}

// ---- Summary ----

type SummarizeFn func(msgs []openai.ChatCompletionMessage) string

type Summary struct {
	base
	k         int
	summarize SummarizeFn
	summary   string
}

func NewSummary(system string, k int, sf SummarizeFn) *Summary {
	return &Summary{base: base{system: system}, k: k, summarize: sf}
}

func (m *Summary) Append(role, content string) {
	m.msgs = append(m.msgs, openai.ChatCompletionMessage{Role: role, Content: content})
	if len(m.msgs) < m.k {
		return
	}
	newSum := m.summarize(m.msgs)
	if m.summary == "" {
		m.summary = newSum
	} else {
		// 累积叠加，不覆盖：旧摘要的事实不能丢
		m.summary = m.summary + "\n" + newSum
	}
	m.msgs = nil
}

func (m *Summary) Messages() []openai.ChatCompletionMessage {
	out := []openai.ChatCompletionMessage{m.sys()}
	if m.summary != "" {
		out = append(out, openai.ChatCompletionMessage{
			Role:    openai.ChatMessageRoleSystem,
			Content: "历史事实：" + m.summary,
		})
	}
	return append(out, m.msgs...)
}
