"""
专门测试 LongCat-Flash-Lite 是否支持 Function Call
"""

import json
from llm_client import LLMClient
from function_definitions import FUNCTION_DEFINITIONS
from colorama import Fore, Style, init

init(autoreset=True)

print(f"\n{Fore.CYAN}{'='*70}")
print("测试 LongCat-Flash-Lite 的 Function Call 支持")
print(f"{'='*70}{Style.RESET_ALL}\n")

# 初始化客户端
try:
    client = LLMClient()
    print(f"✓ 使用模型: {client.model_id}\n")
except Exception as e:
    print(f"❌ 初始化失败: {e}\n")
    exit(1)

# 测试用例
test_cases = [
    {
        "name": "明确的天气查询",
        "question": "请帮我查询北京今天的天气",
        "expected_function": "get_weather"
    },
    {
        "name": "计算请求",
        "question": "156 除以 12 等于多少？",
        "expected_function": "calculate"
    },
    {
        "name": "数据库搜索",
        "question": "搜索价格在500元以上的产品",
        "expected_function": "search_database"
    }
]

results = []

for i, test in enumerate(test_cases, 1):
    print(f"{Fore.YELLOW}【测试 {i}】{test['name']}{Style.RESET_ALL}")
    print(f"问题: {test['question']}")
    print(f"期望调用: {test['expected_function']}\n")
    
    try:
        # 发送请求
        response = client.chat_completion(
            messages=[{"role": "user", "content": test['question']}],
            functions=FUNCTION_DEFINITIONS,
            function_call="auto"
        )
        
        # 检查是否调用了函数
        function_call = client.extract_function_call(response)
        
        if function_call:
            print(f"{Fore.GREEN}✓ 模型调用了函数{Style.RESET_ALL}")
            print(f"  函数名: {function_call['name']}")
            print(f"  参数: {function_call['arguments']}\n")
            
            results.append({
                "test": test['name'],
                "called": True,
                "function": function_call['name'],
                "correct": function_call['name'] == test['expected_function']
            })
        else:
            content = client.get_message_content(response)
            print(f"{Fore.RED}✗ 模型没有调用函数{Style.RESET_ALL}")
            print(f"  直接回答: {content[:100]}...\n")
            
            results.append({
                "test": test['name'],
                "called": False,
                "function": None,
                "correct": False
            })
    
    except Exception as e:
        print(f"{Fore.RED}❌ 测试失败: {str(e)}{Style.RESET_ALL}\n")
        results.append({
            "test": test['name'],
            "called": False,
            "function": None,
            "correct": False,
            "error": str(e)
        })

# 统计结果
print(f"\n{Fore.CYAN}{'='*70}")
print("测试结果统计")
print(f"{'='*70}{Style.RESET_ALL}\n")

total = len(results)
called = sum(1 for r in results if r['called'])
correct = sum(1 for r in results if r['correct'])

print(f"总测试数: {total}")
print(f"调用函数: {called} / {total}")
print(f"调用正确: {correct} / {total}\n")

if called == 0:
    print(f"{Fore.RED}结论: LongCat-Flash-Lite 不支持 Function Call{Style.RESET_ALL}")
    print("或者需要特殊的配置/格式\n")
    
    print(f"{Fore.YELLOW}可能的原因：{Style.RESET_ALL}")
    print("1. 模型本身不支持 Function Call")
    print("2. 需要使用不同的 API 格式")
    print("3. 需要特殊的参数配置")
    print("4. 模型版本问题（Lite 版本可能不支持）\n")
    
elif called < total:
    print(f"{Fore.YELLOW}结论: LongCat-Flash-Lite 部分支持 Function Call{Style.RESET_ALL}")
    print("但可能不够稳定或准确\n")
    
else:
    print(f"{Fore.GREEN}结论: LongCat-Flash-Lite 支持 Function Call{Style.RESET_ALL}")
    if correct == total:
        print("并且调用准确！\n")
    else:
        print("但调用准确性有待提高\n")

# 详细结果
print(f"{Fore.CYAN}详细结果：{Style.RESET_ALL}\n")
for r in results:
    status = f"{Fore.GREEN}✓" if r['called'] else f"{Fore.RED}✗"
    print(f"{status} {r['test']}{Style.RESET_ALL}")
    if r['called']:
        print(f"  调用: {r['function']}")
        print(f"  正确: {'是' if r['correct'] else '否'}")
    else:
        print(f"  未调用函数")
    print()

print(f"{Fore.CYAN}{'='*70}")
print("建议")
print(f"{'='*70}{Style.RESET_ALL}\n")

if called == 0:
    print("如果你需要 Function Call 功能，建议：")
    print("1. 在 Cherry Studio 中配置支持 Function Call 的模型")
    print("   推荐：OpenAI GPT-4、智谱 GLM-4、通义千问")
    print("2. 或者使用 Prompt Engineering 模拟（运行 prompt_based_function_call.py）")
    print("3. 继续使用模拟示例学习原理（运行 simple_example.py）\n")
else:
    print("LongCat-Flash-Lite 有一定的 Function Call 能力！")
    print("可以继续使用，但建议测试更多场景确认稳定性。\n")
