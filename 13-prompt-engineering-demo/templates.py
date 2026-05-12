"""
Prompt 模板库
可复用的 Prompt 模板，适用于常见任务
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
                "max_tokens": 800
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"❌ API 错误: {response.status_code}"
    except Exception as e:
        return f"❌ 调用失败: {e}"


# ============================================
# 模板库
# ============================================

class PromptTemplates:
    """Prompt 模板库"""
    
    @staticmethod
    def code_review(code: str, language: str = "Python") -> tuple[str, str]:
        """代码审查模板"""
        system = f"""你是资深 {language} 工程师，专注代码质量。

审查标准:
- 代码规范和风格
- 性能优化机会
- 安全漏洞
- 最佳实践

输出格式:
【总体评分】: X/10
【优点】:
- 优点1
- 优点2

【问题】:
1. [严重程度] 问题描述
   改进建议: 具体建议

【总结】: 一句话总结
"""
        
        user = f"""审查以下代码:

```{language.lower()}
{code}
```
"""
        return system, user
    
    @staticmethod
    def data_extraction(text: str, fields: list[str]) -> tuple[str, str]:
        """数据提取模板"""
        system = "你是数据提取专家，从非结构化文本中提取结构化信息。"
        
        fields_str = ", ".join([f'"{f}"' for f in fields])
        
        user = f"""从文本中提取以下字段: {fields_str}

输出 JSON 格式。

示例:
输入: "张三，28岁，Python工程师"
输出: {{"name": "张三", "age": 28, "position": "Python工程师"}}

现在处理:
输入: {text}
输出:"""
        
        return system, user
    
    @staticmethod
    def translation(text: str, source_lang: str = "中文", target_lang: str = "英文") -> tuple[str, str]:
        """翻译模板"""
        system = f"""你是专业翻译，将 {source_lang} 翻译成地道的 {target_lang}。

要求:
- 保持原意
- 使用地道表达
- 注意语境和文化差异
"""
        
        user = f"翻译: {text}"
        
        return system, user
    
    @staticmethod
    def summarization(text: str, max_words: int = 100) -> tuple[str, str]:
        """摘要模板"""
        system = f"""你是内容摘要专家。

要求:
- 提取核心信息
- 保持客观准确
- 控制在 {max_words} 字以内
"""
        
        user = f"""总结以下内容:

{text}

摘要:"""
        
        return system, user
    
    @staticmethod
    def bug_analysis(error_message: str, code: str = "") -> tuple[str, str]:
        """Bug 分析模板"""
        system = """你是调试专家，帮助分析和解决代码问题。

输出格式:
【问题原因】: 简要说明
【解决方案】: 具体步骤
【修改后代码】: 完整代码
【预防措施】: 如何避免类似问题
"""
        
        user = f"""分析以下错误:

错误信息:
{error_message}
"""
        
        if code:
            user += f"""
相关代码:
```
{code}
```
"""
        
        return system, user
    
    @staticmethod
    def api_documentation(function_signature: str, description: str = "") -> tuple[str, str]:
        """API 文档生成模板"""
        system = """你是技术文档专家，生成清晰的 API 文档。

格式:
## 函数名

**描述**: 简要说明

**参数**:
- `param1` (type): 说明
- `param2` (type): 说明

**返回值**: 返回值说明

**示例**:
```python
# 使用示例
```

**注意事项**:
- 注意点1
- 注意点2
"""
        
        user = f"""为以下函数生成文档:

```python
{function_signature}
```
"""
        
        if description:
            user += f"\n函数说明: {description}"
        
        return system, user
    
    @staticmethod
    def test_case_generation(function_code: str) -> tuple[str, str]:
        """测试用例生成模板"""
        system = """你是测试工程师，生成全面的测试用例。

要求:
- 正常情况测试
- 边界条件测试
- 异常情况测试
- 使用 pytest 框架
"""
        
        user = f"""为以下函数生成测试用例:

```python
{function_code}
```

生成完整的 pytest 测试代码。
"""
        
        return system, user


# ============================================
# 演示
# ============================================

def print_section(title: str):
    """打印分节标题"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{title}")
    print(f"{'='*60}{Style.RESET_ALL}\n")


def demo_template(name: str, system: str, user: str):
    """演示模板"""
    print(f"{Fore.GREEN}模板: {name}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}System Prompt:{Style.RESET_ALL}")
    print(f"{system}\n")
    
    print(f"{Fore.YELLOW}User Prompt:{Style.RESET_ALL}")
    print(f"{user}\n")
    
    print(f"{Fore.CYAN}正在调用 LLM...{Style.RESET_ALL}\n")
    response = call_llm(system, user)
    
    print(f"{Fore.CYAN}回答:{Style.RESET_ALL}")
    print(response)
    print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")


def main():
    print_section("Prompt 模板库演示")
    
    templates = PromptTemplates()
    
    # 1. 代码审查
    print_section("1. 代码审查模板")
    code = """
def calculate_discount(price, discount_rate):
    return price * discount_rate
"""
    system, user = templates.code_review(code)
    demo_template("代码审查", system, user)
    
    # 2. 数据提取
    print_section("2. 数据提取模板")
    text = "李四，32岁，高级Java工程师，邮箱 lisi@company.com，擅长 Spring Boot 和微服务"
    system, user = templates.data_extraction(text, ["name", "age", "position", "email", "skills"])
    demo_template("数据提取", system, user)
    
    # 3. 翻译
    print_section("3. 翻译模板")
    text = "这个功能非常实用，大大提高了开发效率"
    system, user = templates.translation(text)
    demo_template("翻译", system, user)
    
    # 4. Bug 分析
    print_section("4. Bug 分析模板")
    error = "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
    code = """
def add_numbers(a, b):
    return a + b

result = add_numbers(10, "20")
"""
    system, user = templates.bug_analysis(error, code)
    demo_template("Bug 分析", system, user)
    
    # 总结
    print_section("模板使用指南")
    
    print(f"{Fore.GREEN}如何使用这些模板:{Style.RESET_ALL}\n")
    
    print("1. 直接使用:")
    print("   system, user = PromptTemplates.code_review(code)")
    print("   response = call_llm(system, user)\n")
    
    print("2. 自定义修改:")
    print("   - 调整 System Prompt 的角色定义")
    print("   - 修改输出格式要求")
    print("   - 添加具体的业务规则\n")
    
    print("3. 组合使用:")
    print("   - 先用数据提取模板提取信息")
    print("   - 再用翻译模板翻译结果")
    print("   - 最后用摘要模板生成总结\n")
    
    print(f"{Fore.YELLOW}核心原则:{Style.RESET_ALL}")
    print("  - 模板是起点，不是终点")
    print("  - 根据实际需求调整")
    print("  - 测试并迭代优化\n")


if __name__ == "__main__":
    main()
