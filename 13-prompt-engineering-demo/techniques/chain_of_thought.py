"""
Chain of Thought (CoT) 技术演示
让模型展示推理过程，提高准确率
"""

import os
import requests
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 600
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"❌ API 错误: {response.status_code}"
    except Exception as e:
        return f"❌ 调用失败: {e}"


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{title}")
    print(f"{'='*60}{Style.RESET_ALL}\n")


def main():
    print_section("Chain of Thought (CoT) 技术演示")
    
    # 任务 1: 数学推理
    print_section("任务 1: 数学推理")
    
    problem = "一个班级有 45 个学生，其中 60% 是女生。如果新来 5 个男生，现在男生占多少比例？"
    
    # 不使用 CoT
    print(f"{Fore.GREEN}❌ 不使用 CoT（直接问答）{Style.RESET_ALL}\n")
    prompt_direct = problem
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL} {prompt_direct}\n")
    
    response = call_llm("", prompt_direct)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 使用 CoT
    print(f"{Fore.GREEN}✅ 使用 CoT（展示推理过程）{Style.RESET_ALL}\n")
    prompt_cot = f"""请一步步思考并解答：

问题: {problem}

思考过程:
1. 首先计算原来的男女生人数
2. 然后计算新来男生后的总人数
3. 计算新的男生人数
4. 最后计算男生比例

详细推理:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_cot)
    print()
    
    response = call_llm("", prompt_cot)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 任务 2: 逻辑推理
    print_section("任务 2: 逻辑推理")
    
    logic_problem = """有三个盒子：红、蓝、绿。
- 红盒子上写着"宝石在这里"
- 蓝盒子上写着"宝石不在红盒子"
- 绿盒子上写着"宝石不在这里"

已知只有一个盒子的标签是真的，宝石在哪个盒子？"""
    
    # 不使用 CoT
    print(f"{Fore.GREEN}❌ 不使用 CoT{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL} {logic_problem}\n")
    
    response = call_llm("", logic_problem)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 使用 CoT
    print(f"{Fore.GREEN}✅ 使用 CoT{Style.RESET_ALL}\n")
    prompt_logic_cot = f"""{logic_problem}

请逐步分析：

步骤1: 列出所有可能的情况
步骤2: 假设每个盒子的标签是真的，检查是否矛盾
步骤3: 找出唯一不矛盾的情况
步骤4: 得出结论

详细推理:"""
    print(f"{Fore.YELLOW}Prompt:{Style.RESET_ALL}")
    print(prompt_logic_cot[:100] + "...")
    print()
    
    response = call_llm("", prompt_logic_cot)
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 总结
    print_section("Chain of Thought 要点")
    
    print(f"{Fore.GREEN}✓ CoT 的核心价值:{Style.RESET_ALL}\n")
    print("1. 提高准确率 - 特别是复杂推理任务")
    print("2. 可验证性 - 能看到推理过程")
    print("3. 可调试性 - 发现错误在哪一步")
    print("4. 可解释性 - 理解 AI 的思考\n")
    
    print(f"{Fore.YELLOW}适用场景:{Style.RESET_ALL}\n")
    print("✅ 数学计算")
    print("✅ 逻辑推理")
    print("✅ 多步骤问题")
    print("✅ 需要验证的任务")
    print("❌ 简单查询（浪费 token）")
    print("❌ 创意写作（限制发挥）\n")
    
    print(f"{Fore.GREEN}✓ CoT 的实现方式:{Style.RESET_ALL}\n")
    print("1. 显式引导:")
    print("   \"请一步步思考\"")
    print("   \"详细说明推理过程\"\n")
    
    print("2. 结构化步骤:")
    print("   \"步骤1: ...\"")
    print("   \"步骤2: ...\"")
    print("   \"步骤3: ...\"\n")
    
    print("3. Few-shot CoT:")
    print("   提供带推理过程的示例\n")
    
    print(f"{Fore.YELLOW}效果对比:{Style.RESET_ALL}\n")
    print("直接问答:")
    print("  → 快速，但可能出错")
    print("  → 无法验证推理\n")
    
    print("Chain of Thought:")
    print("  → 准确率提升 20-40%")
    print("  → 推理过程透明")
    print("  → 更容易发现和修正错误\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}记住: 让 AI 「说出」思考过程{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
