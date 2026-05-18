// tools.go —— 工具注册表，沿用 01 demo 的写法。
// 这里只放一个 get_weather，演示流式 + 工具的 delta 累积就够了。
package main

import (
	"encoding/json"
	"fmt"

	"github.com/sashabaranov/go-openai"
	"github.com/sashabaranov/go-openai/jsonschema"
)

type toolFn func(args map[string]any) any

type tool struct {
	def openai.Tool
	fn  toolFn
}

var registry = map[string]tool{}

func register(name, desc string, params jsonschema.Definition, fn toolFn) {
	registry[name] = tool{
		def: openai.Tool{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name: name, Description: desc, Parameters: params,
			},
		},
		fn: fn,
	}
}

func schemas() []openai.Tool {
	out := make([]openai.Tool, 0, len(registry))
	for _, t := range registry {
		out = append(out, t.def)
	}
	return out
}

func call(name, argsJSON string) string {
	t, ok := registry[name]
	if !ok {
		return errJSON(fmt.Sprintf("unknown tool: %s", name))
	}
	var args map[string]any
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return errJSON(err.Error())
	}
	b, _ := json.Marshal(t.fn(args))
	return string(b)
}

func errJSON(msg string) string {
	b, _ := json.Marshal(map[string]string{"error": msg})
	return string(b)
}

func init() {
	register("get_weather", "获取指定城市的天气",
		jsonschema.Definition{
			Type: jsonschema.Object,
			Properties: map[string]jsonschema.Definition{
				"city": {Type: jsonschema.String, Description: "城市名"},
			},
			Required: []string{"city"},
		},
		func(args map[string]any) any {
			db := map[string]struct {
				t    int
				cond string
			}{"北京": {15, "晴"}, "上海": {20, "多云"}, "深圳": {25, "小雨"}}
			city, _ := args["city"].(string)
			w, ok := db[city]
			if !ok {
				w.t, w.cond = 18, "数据不可用"
			}
			return map[string]any{"city": city, "temperature": w.t, "condition": w.cond}
		},
	)
}
