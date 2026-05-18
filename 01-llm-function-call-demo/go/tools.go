// tools.go —— 工具注册表：函数本体 + JSON Schema 配在一起。
// 加新工具只需在 init() 里加一个 register(...) 调用；client/main 都不用改。
package main

import (
	"encoding/json"
	"fmt"
	"strings"

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
				Name:        name,
				Description: desc,
				Parameters:  params,
			},
		},
		fn: fn,
	}
}

// schemas 返回给 LLM 的 tools 字段。
func schemas() []openai.Tool {
	out := make([]openai.Tool, 0, len(registry))
	for _, t := range registry {
		out = append(out, t.def)
	}
	return out
}

// call 执行一次工具调用，返回 JSON 字符串（OpenAI tool message 要的格式）。
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

// ---- 三个示例工具 ----

type product struct {
	ID    int    `json:"id"`
	Name  string `json:"name"`
	Price int    `json:"price"`
}

var products = []product{
	{1, "笔记本电脑", 5999},
	{2, "机械键盘", 599},
	{3, "无线鼠标", 199},
}

func init() {
	register("get_weather", "获取指定城市的天气",
		jsonschema.Definition{
			Type: jsonschema.Object,
			Properties: map[string]jsonschema.Definition{
				"city": {Type: jsonschema.String, Description: "城市名，如：北京"},
				"unit": {Type: jsonschema.String, Enum: []string{"celsius", "fahrenheit"}},
			},
			Required: []string{"city"},
		},
		func(args map[string]any) any {
			db := map[string]struct {
				c    float64
				cond string
			}{"北京": {25, "晴"}, "上海": {28, "多云"}, "深圳": {30, "小雨"}}
			city, _ := args["city"].(string)
			w, ok := db[city]
			if !ok {
				w.c, w.cond = 20, "数据不可用"
			}
			temp := w.c
			if unit, _ := args["unit"].(string); unit == "fahrenheit" {
				temp = w.c*9/5 + 32
			}
			return map[string]any{"city": city, "temperature": temp, "condition": w.cond}
		},
	)

	register("calculate", "执行四则运算",
		jsonschema.Definition{
			Type: jsonschema.Object,
			Properties: map[string]jsonschema.Definition{
				"op": {Type: jsonschema.String, Enum: []string{"add", "sub", "mul", "div"}},
				"a":  {Type: jsonschema.Number},
				"b":  {Type: jsonschema.Number},
			},
			Required: []string{"op", "a", "b"},
		},
		func(args map[string]any) any {
			op, _ := args["op"].(string)
			a, _ := args["a"].(float64)
			b, _ := args["b"].(float64)
			switch op {
			case "add":
				return map[string]any{"result": a + b}
			case "sub":
				return map[string]any{"result": a - b}
			case "mul":
				return map[string]any{"result": a * b}
			case "div":
				if b == 0 {
					return map[string]any{"error": "division by zero"}
				}
				return map[string]any{"result": a / b}
			}
			return map[string]any{"error": "unknown op: " + op}
		},
	)

	// 让 LLM 自己拆"价格 500 以上" -> min_price=500，不要在 Go 里重做 NLP。
	register("search_products", "搜索产品。可按关键词和价格区间过滤。",
		jsonschema.Definition{
			Type: jsonschema.Object,
			Properties: map[string]jsonschema.Definition{
				"query":     {Type: jsonschema.String, Description: "关键词，留空匹配全部"},
				"min_price": {Type: jsonschema.Number},
				"max_price": {Type: jsonschema.Number},
			},
		},
		func(args map[string]any) any {
			query, _ := args["query"].(string)
			minP, _ := args["min_price"].(float64)
			maxP, ok := args["max_price"].(float64)
			if !ok {
				maxP = 1e18
			}
			hits := []product{}
			for _, p := range products {
				if (query == "" || strings.Contains(p.Name, query)) && float64(p.Price) >= minP && float64(p.Price) <= maxP {
					hits = append(hits, p)
				}
			}
			return map[string]any{"count": len(hits), "results": hits}
		},
	)
}
