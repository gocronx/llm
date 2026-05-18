// schemas.go —— 三个示例 JSON Schema。
//
// OpenAI strict 模式硬规则：每个 object 都得有 additionalProperties:false；
// required 必须列出 properties 里全部 key；不支持 default / format。
package main

func schemaResume() map[string]any {
	return obj(
		props{
			"name":     {"type": "string"},
			"age":      {"type": "integer"},
			"position": {"type": "string"},
			"email":    {"type": "string"},
			"skills":   {"type": "array", "items": map[string]any{"type": "string"}},
		},
		[]string{"name", "age", "position", "email", "skills"},
	)
}

func schemaProduct() map[string]any {
	price := obj(
		props{
			"amount":   {"type": "number"},
			"currency": {"type": "string", "enum": []string{"CNY", "USD", "EUR"}},
		},
		[]string{"amount", "currency"},
	)
	return obj(
		props{
			"name":     {"type": "string"},
			"brand":    {"type": "string"},
			"price":    price,
			"in_stock": {"type": "boolean"},
		},
		[]string{"name", "brand", "price", "in_stock"},
	)
}

func schemaSentiment() map[string]any {
	return obj(
		props{
			"label":      {"type": "string", "enum": []string{"positive", "neutral", "negative"}},
			"confidence": {"type": "number"},
			"reason":     {"type": "string"},
		},
		[]string{"label", "confidence", "reason"},
	)
}

// 把"声明 schema 时填三遍 additionalProperties:false"这种噪音抹掉
type props map[string]map[string]any

func obj(p props, required []string) map[string]any {
	propsAny := map[string]any{}
	for k, v := range p {
		propsAny[k] = v
	}
	return map[string]any{
		"type":                 "object",
		"properties":           propsAny,
		"required":             required,
		"additionalProperties": false,
	}
}
