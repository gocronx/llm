package main

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// API 请求和响应结构
type Message struct {
	Role       string      `json:"role"`
	Content    string      `json:"content,omitempty"`
	ToolCalls  []ToolCall  `json:"tool_calls,omitempty"`
	ToolCallID string      `json:"tool_call_id,omitempty"`
	Name       string      `json:"name,omitempty"`
}

type ToolCall struct {
	ID       string   `json:"id"`
	Type     string   `json:"type"`
	Function Function `json:"function"`
}

type Function struct {
	Name      string `json:"name"`
	Arguments string `json:"arguments"`
}

type Tool struct {
	Type     string             `json:"type"`
	Function FunctionDefinition `json:"function"`
}

type ChatRequest struct {
	Model     string    `json:"model"`
	Messages  []Message `json:"messages"`
	Tools     []Tool    `json:"tools,omitempty"`
	MaxTokens int       `json:"max_tokens"`
}

type ChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

// FunctionDefinition 函数定义结构
type FunctionDefinition struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  map[string]interface{} `json:"parameters"`
}

// GetWeather 获取天气信息（模拟）
func GetWeather(city string, unit string) string {
	if unit == "" {
		unit = "celsius"
	}

	weatherData := map[string]map[string]interface{}{
		"北京": {"condition": "晴天", "temp_c": 25, "temp_f": 77, "humidity": 45},
		"上海": {"condition": "多云", "temp_c": 28, "temp_f": 82, "humidity": 65},
		"深圳": {"condition": "小雨", "temp_c": 30, "temp_f": 86, "humidity": 80},
	}

	cityData, exists := weatherData[city]
	if !exists {
		cityData = map[string]interface{}{
			"condition": "数据不可用",
			"temp_c":    20,
			"temp_f":    68,
			"humidity":  50,
		}
	}

	var temp interface{}
	var tempUnit string
	if unit == "celsius" {
		temp = cityData["temp_c"]
		tempUnit = "°C"
	} else {
		temp = cityData["temp_f"]
		tempUnit = "°F"
	}

	result := map[string]interface{}{
		"city":        city,
		"condition":   cityData["condition"],
		"temperature": fmt.Sprintf("%v%s", temp, tempUnit),
		"humidity":    fmt.Sprintf("%v%%", cityData["humidity"]),
		"timestamp":   time.Now().Format("2006-01-02 15:04:05"),
	}

	jsonData, _ := json.Marshal(result)
	return string(jsonData)
}

// Calculate 执行数学计算
func Calculate(operation string, a, b float64) string {
	var result interface{}

	switch operation {
	case "add":
		result = a + b
	case "subtract":
		result = a - b
	case "multiply":
		result = a * b
	case "divide":
		if b != 0 {
			result = a / b
		} else {
			result = "错误：除数不能为零"
		}
	default:
		result = "不支持的运算"
	}

	response := map[string]interface{}{
		"operation": operation,
		"operand_a": a,
		"operand_b": b,
		"result":    result,
	}

	jsonData, _ := json.Marshal(response)
	return string(jsonData)
}

// SearchDatabase 搜索数据库（模拟）
func SearchDatabase(query string, category string) string {
	if category == "" {
		category = "all"
	}

	database := map[string][]map[string]interface{}{
		"products": {
			{"id": 1, "name": "笔记本电脑", "price": 5999},
			{"id": 2, "name": "机械键盘", "price": 599},
			{"id": 3, "name": "无线鼠标", "price": 199},
		},
		"users": {
			{"id": 1, "name": "张三", "email": "zhangsan@example.com"},
			{"id": 2, "name": "李四", "email": "lisi@example.com"},
		},
		"orders": {
			{"id": 1001, "user": "张三", "product": "笔记本电脑", "status": "已发货"},
			{"id": 1002, "user": "李四", "product": "机械键盘", "status": "处理中"},
		},
	}

	results := []map[string]interface{}{}
	searchCategories := []string{}

	if category == "all" {
		for cat := range database {
			searchCategories = append(searchCategories, cat)
		}
	} else {
		searchCategories = []string{category}
	}

	// 解析价格范围查询
	minPrice, maxPrice, hasPriceFilter := parsePriceQuery(query)

	for _, cat := range searchCategories {
		if items, exists := database[cat]; exists {
			for _, item := range items {
				matched := false

				// 如果有价格过滤条件且是产品类别
				if hasPriceFilter && cat == "products" {
					if price, ok := item["price"].(int); ok {
						matched = price >= minPrice && price <= maxPrice
					}
				} else {
					// 普通字符串搜索
					itemJSON, _ := json.Marshal(item)
					matched = contains(string(itemJSON), query)
				}

				if matched {
					itemCopy := make(map[string]interface{})
					for k, v := range item {
						itemCopy[k] = v
					}
					itemCopy["category"] = cat
					results = append(results, itemCopy)
				}
			}
		}
	}

	response := map[string]interface{}{
		"query":    query,
		"category": category,
		"results":  results,
		"count":    len(results),
	}

	jsonData, _ := json.Marshal(response)
	return string(jsonData)
}

// parsePriceQuery 解析价格查询（返回 min, max, hasPriceFilter）
func parsePriceQuery(query string) (int, int, bool) {
	queryLower := strings.ToLower(query)

	// 提取数字
	var price int
	for i := 0; i < len(query); i++ {
		if query[i] >= '0' && query[i] <= '9' {
			numStr := ""
			for i < len(query) && query[i] >= '0' && query[i] <= '9' {
				numStr += string(query[i])
				i++
			}
			price, _ = strconv.Atoi(numStr)
			break
		}
	}

	if price == 0 {
		return 0, 0, false
	}

	// 判断是"以上"还是"以下"
	if strings.Contains(queryLower, "以上") || strings.Contains(queryLower, "大于") || strings.Contains(queryLower, ">") {
		return price, int(^uint(0) >> 1), true // 返回最大int值
	} else if strings.Contains(queryLower, "以下") || strings.Contains(queryLower, "小于") || strings.Contains(queryLower, "<") {
		return 0, price, true
	} else if strings.Contains(queryLower, "价格") {
		// 如果只提到"价格XXX"，默认查找该价格附近的（±100）
		return price - 100, price + 100, true
	}

	return 0, 0, false
}

// ExecuteFunction 执行函数
func ExecuteFunction(functionName string, arguments map[string]interface{}) string {
	switch functionName {
	case "get_weather":
		city := arguments["city"].(string)
		unit := ""
		if u, ok := arguments["unit"].(string); ok {
			unit = u
		}
		return GetWeather(city, unit)

	case "calculate":
		operation := arguments["operation"].(string)
		a := arguments["a"].(float64)
		b := arguments["b"].(float64)
		return Calculate(operation, a, b)

	case "search_database":
		query := arguments["query"].(string)
		category := ""
		if c, ok := arguments["category"].(string); ok {
			category = c
		}
		return SearchDatabase(query, category)

	default:
		return fmt.Sprintf(`{"error": "未找到函数: %s"}`, functionName)
	}
}

// FunctionDefinitions 函数定义列表
var FunctionDefinitions = []FunctionDefinition{
	{
		Name:        "get_weather",
		Description: "获取指定城市的天气信息",
		Parameters: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"city": map[string]interface{}{
					"type":        "string",
					"description": "城市名称，如：北京、上海",
				},
				"unit": map[string]interface{}{
					"type":        "string",
					"enum":        []string{"celsius", "fahrenheit"},
					"description": "温度单位",
				},
			},
			"required": []string{"city"},
		},
	},
	{
		Name:        "calculate",
		Description: "执行数学运算",
		Parameters: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"operation": map[string]interface{}{
					"type":        "string",
					"enum":        []string{"add", "subtract", "multiply", "divide"},
					"description": "运算类型",
				},
				"a": map[string]interface{}{
					"type":        "number",
					"description": "第一个数",
				},
				"b": map[string]interface{}{
					"type":        "number",
					"description": "第二个数",
				},
			},
			"required": []string{"operation", "a", "b"},
		},
	},
	{
		Name:        "search_database",
		Description: "搜索数据库",
		Parameters: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"query": map[string]interface{}{
					"type":        "string",
					"description": "搜索关键词",
				},
				"category": map[string]interface{}{
					"type":        "string",
					"enum":        []string{"all", "products", "users", "orders"},
					"description": "搜索类别",
				},
			},
			"required": []string{"query"},
		},
	},
}

// 辅助函数
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && 
		(s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || 
		containsMiddle(s, substr)))
}

func containsMiddle(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
