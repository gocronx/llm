"""
实战案例: 代码审查 Agent
自动审查代码，检测问题，提供修复建议
"""

import os
import json
from typing import Dict, Any
from agent import Agent
from colorama import Fore, Style, init

init(autoreset=True)


class CodeReviewAgent(Agent):
    """代码审查 Agent"""
    
    def __init__(self, max_iterations: int = 10):
        # 定义代码审查工具
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_code_file",
                    "description": "读取代码文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "代码文件路径"
                            }
                        },
                        "required": ["filepath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_security",
                    "description": "检查代码安全问题（SQL注入、XSS、硬编码密码等），返回发现的所有安全问题",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "要检查的代码"
                            }
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_performance",
                    "description": "检查代码性能问题（循环嵌套、重复计算等），返回发现的所有性能问题",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "要检查的代码"
                            }
                        },
                        "required": ["code"]
                    }
                }
            }
        ]
        
        super().__init__(tools, max_iterations)
        
        # 修改 system prompt 为代码审查专家
        self.system_prompt = """你是专业的代码审查 Agent。

                                你的工作流程:
                                1. 读取代码文件
                                2. 检查安全问题
                                3. 检查性能问题
                                4. 对发现的问题提供修复建议
                                5. 生成完整的审查报告

                                审查标准:
                                - 安全性（SQL注入、XSS、硬编码密码）
                                - 性能（循环嵌套、重复计算）
                                - 代码质量（命名、注释、结构）

                                重要: 完成所有检查后，必须生成最终的审查报告，不要继续调用工具。

                                输出格式:
                                【严重程度】: critical/high/medium/low
                                【安全问题】:
                                1. [严重程度] 问题描述
                                修复建议: 具体建议

                                【性能问题】:
                                1. [严重程度] 问题描述
                                修复建议: 具体建议
                                
                                【总结】: 总体评价和建议
                            """
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """执行工具"""
        
        if tool_name == "read_code_file":
            filepath = arguments["filepath"]
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    "filepath": filepath,
                    "content": content,
                    "lines": len(content.split('\n'))
                }
            except Exception as e:
                return {"error": f"读取文件失败: {e}"}
        
        elif tool_name == "check_security":
            code = arguments["code"]
            issues = []
            
            # 简单的安全检查（实际应该用专业工具）
            if "password" in code.lower() and ("=" in code or "==" in code):
                if any(pwd in code for pwd in ['"123', "'123", '"admin', "'admin"]):
                    issues.append({
                        "type": "security",
                        "severity": "critical",
                        "issue": "硬编码密码",
                        "description": "代码中包含硬编码的密码",
                        "suggestion": "使用环境变量或配置文件存储密码，使用哈希算法（如bcrypt）存储密码"
                    })
            
            if "SELECT" in code and "+" in code:
                issues.append({
                    "type": "security",
                    "severity": "high",
                    "issue": "SQL注入风险",
                    "description": "使用字符串拼接构建SQL查询",
                    "suggestion": "使用参数化查询或ORM，避免字符串拼接"
                })
            
            if "<script>" in code.lower() or "eval(" in code:
                issues.append({
                    "type": "security",
                    "severity": "high",
                    "issue": "XSS风险",
                    "description": "可能存在跨站脚本攻击风险",
                    "suggestion": "对用户输入进行转义，使用安全的模板引擎"
                })
            
            return {
                "checked": True,
                "issues_found": len(issues),
                "issues": issues
            }
        
        elif tool_name == "check_performance":
            code = arguments["code"]
            issues = []
            
            # 简单的性能检查
            lines = code.split('\n')
            indent_levels = []
            for line in lines:
                if 'for ' in line or 'while ' in line:
                    indent = len(line) - len(line.lstrip())
                    indent_levels.append(indent)
            
            # 检查嵌套循环
            if len(indent_levels) > 1:
                for i in range(len(indent_levels) - 1):
                    if indent_levels[i+1] > indent_levels[i]:
                        issues.append({
                            "type": "performance",
                            "severity": "medium",
                            "issue": "嵌套循环",
                            "description": "存在嵌套循环，可能影响性能",
                            "suggestion": "考虑使用哈希表优化，或使用列表推导式"
                        })
                        break
            
            # 检查重复计算
            if code.count('len(') > 2:
                issues.append({
                    "type": "performance",
                    "severity": "low",
                    "issue": "重复计算",
                    "description": "多次调用len()，建议缓存结果",
                    "suggestion": "将len()结果缓存到变量中"
                })
            
            return {
                "checked": True,
                "issues_found": len(issues),
                "issues": issues
            }
        
        else:
            return {"error": f"未知工具: {tool_name}"}
    
    def run(self, filepath: str, verbose: bool = True) -> str:
        """运行代码审查"""
        task = f"请审查代码文件: {filepath}"
        
        # 使用自定义的 system prompt
        self.memory = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task}
        ]
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"代码审查 Agent")
            print(f"文件: {filepath}")
            print(f"{'='*60}\n")
        
        # 调用父类的迭代逻辑
        return super().run(task, verbose)


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{title}")
    print(f"{'='*60}{Style.RESET_ALL}\n")


def main():
    print_section("代码审查 Agent 演示")
    
    # 创建测试代码文件
    test_code = '''
                def login(username, password):
                    # 硬编码密码 - 安全问题
                    if username == "admin" and password == "123456":
                        return True
                    
                    # SQL注入风险 - 安全问题
                    query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
                    result = db.execute(query)
                    
                    return result is not None

                def find_duplicates(items):
                    # 嵌套循环 - 性能问题
                    duplicates = []
                    for i in range(len(items)):  # 重复计算 len(items)
                        for j in range(i+1, len(items)):  # 重复计算 len(items)
                            if items[i] == items[j]:
                                duplicates.append(items[i])
                    return duplicates
               '''
    
    # 保存测试代码
    test_file = "test_code.py"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    print(f"{Fore.YELLOW}测试代码:{Style.RESET_ALL}")
    print(test_code)
    
    # 创建代码审查 Agent
    agent = CodeReviewAgent(max_iterations=15)
    
    # 运行审查
    result = agent.run(test_file, verbose=True)
    
    # 清理测试文件
    os.remove(test_file)
    
    # 总结
    print_section("Agent 工作流程")
    
    print(f"{Fore.GREEN}实际执行步骤:{Style.RESET_ALL}\n")
    
    tool_calls = agent.get_tool_calls()
    for i, call in enumerate(tool_calls, 1):
        print(f"{i}. {call['tool']}")
        print(f"   参数: {json.dumps(call['arguments'], ensure_ascii=False)[:80]}...")
        print(f"   结果: {str(call['result'])[:80]}...\n")
    
    print(f"{Fore.YELLOW}Agent 的价值:{Style.RESET_ALL}\n")
    print("✓ 自动化 - 无需人工逐步操作")
    print("✓ 全面性 - 自动检查多个方面")
    print("✓ 一致性 - 每次审查标准相同")
    print("✓ 可扩展 - 容易添加新的检查工具\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Agent 让复杂任务自动化{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
