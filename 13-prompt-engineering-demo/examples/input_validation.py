"""
实战案例: 输入验证
使用 LLM 验证和清洗用户输入
"""

import os
import json
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
                "temperature": 0.3,  # 低温度，更确定性
                "max_tokens": 500
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


def validate_input(user_input: str, validation_type: str) -> dict:
    """
    验证用户输入
    
    使用的 Prompt Engineering 技术:
    1. System Prompt - 定义验证专家角色
    2. Structured Output - JSON 格式输出
    3. Few-shot - 提供验证示例
    4. 明确规则 - 具体的验证标准
    """
    
    # System Prompt: 定义角色和行为
    system = """你是输入验证专家，负责验证和清洗用户输入。

你的职责:
1. 检查输入是否符合要求
2. 识别潜在的安全风险（SQL注入、XSS、命令注入）
3. 提取和标准化有效信息
4. 给出清晰的错误提示

你的原则:
- 严格但友好
- 安全第一
- 给出具体的改进建议
"""
    
    # 根据验证类型选择不同的 Prompt
    if validation_type == "email":
        user = f"""验证邮箱地址并输出 JSON:

{{
  "valid": true/false,
  "normalized": "标准化后的邮箱（如果有效）",
  "issues": ["问题1", "问题2"],
  "suggestion": "改进建议"
}}

验证规则:
- 必须包含 @ 符号
- @ 前后都要有内容
- 域名部分要有 . 符号
- 不能包含空格和特殊字符（除了 . _ - +）

示例:
输入: "user@example.com"
输出: {{"valid": true, "normalized": "user@example.com", "issues": [], "suggestion": ""}}

输入: "invalid.email"
输出: {{"valid": false, "normalized": "", "issues": ["缺少 @ 符号"], "suggestion": "邮箱格式应为: username@domain.com"}}

现在验证:
输入: "{user_input}"
输出:"""
    
    elif validation_type == "phone":
        user = f"""验证手机号并输出 JSON:

{{
  "valid": true/false,
  "normalized": "标准化后的手机号（如果有效）",
  "issues": ["问题1", "问题2"],
  "suggestion": "改进建议"
}}

验证规则:
- 中国大陆手机号：11位数字，1开头
- 支持格式：13812345678 或 138-1234-5678 或 138 1234 5678
- 标准化为纯数字格式

示例:
输入: "13812345678"
输出: {{"valid": true, "normalized": "13812345678", "issues": [], "suggestion": ""}}

输入: "138-1234-5678"
输出: {{"valid": true, "normalized": "13812345678", "issues": [], "suggestion": ""}}

输入: "12345"
输出: {{"valid": false, "normalized": "", "issues": ["长度不足11位"], "suggestion": "请输入11位手机号"}}

现在验证:
输入: "{user_input}"
输出:"""
    
    elif validation_type == "sql":
        user = f"""检查 SQL 注入风险并输出 JSON:

{{
  "safe": true/false,
  "risk_level": "safe/low/medium/high/critical",
  "threats": ["威胁1", "威胁2"],
  "sanitized": "清洗后的输入（如果可以清洗）",
  "suggestion": "安全建议"
}}

检查项:
- SQL 关键字（SELECT, DROP, DELETE, UPDATE, INSERT, UNION）
- 注释符号（--, /*, #）
- 引号（', "）
- 分号（;）
- 逻辑运算符（OR, AND）

示例:
输入: "张三"
输出: {{"safe": true, "risk_level": "safe", "threats": [], "sanitized": "张三", "suggestion": ""}}

输入: "admin' OR '1'='1"
输出: {{"safe": false, "risk_level": "critical", "threats": ["包含 SQL 注入特征", "使用了 OR 逻辑", "包含引号"], "sanitized": "", "suggestion": "拒绝此输入，使用参数化查询"}}

现在检查:
输入: "{user_input}"
输出:"""
    
    elif validation_type == "xss":
        user = f"""检查 XSS 攻击风险并输出 JSON:

{{
  "safe": true/false,
  "risk_level": "safe/low/medium/high/critical",
  "threats": ["威胁1", "威胁2"],
  "sanitized": "清洗后的输入（如果可以清洗）",
  "suggestion": "安全建议"
}}

检查项:
- HTML 标签（<script>, <iframe>, <img>, <a>）
- JavaScript 事件（onclick, onerror, onload）
- JavaScript 协议（javascript:）
- 特殊字符（<, >, ", '）

示例:
输入: "Hello World"
输出: {{"safe": true, "risk_level": "safe", "threats": [], "sanitized": "Hello World", "suggestion": ""}}

输入: "<script>alert('XSS')</script>"
输出: {{"safe": false, "risk_level": "critical", "threats": ["包含 script 标签", "可能执行恶意代码"], "sanitized": "", "suggestion": "拒绝此输入或转义所有 HTML 字符"}}

现在检查:
输入: "{user_input}"
输出:"""
    
    else:
        return {"error": "不支持的验证类型"}
    
    response = call_llm(system, user)
    
    # 尝试解析 JSON
    try:
        # 提取 JSON（可能包含在其他文本中）
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        return {"error": "无法解析响应", "raw": response}
    except:
        return {"error": "JSON 解析失败", "raw": response}


def main():
    print_section("实战案例: 输入验证")
    
    # 测试案例 1: 邮箱验证
    print(f"{Fore.GREEN}案例 1: 邮箱验证{Style.RESET_ALL}\n")
    
    test_emails = [
        "user@example.com",           # 有效
        "invalid.email",              # 无效：缺少 @
        "user @example.com",          # 无效：包含空格
        "user@domain",                # 无效：域名格式错误
    ]
    
    for email in test_emails:
        print(f"{Fore.YELLOW}输入:{Style.RESET_ALL} {email}")
        result = validate_input(email, "email")
        
        if "error" not in result:
            status = f"{Fore.GREEN}✓ 有效{Style.RESET_ALL}" if result.get("valid") else f"{Fore.RED}✗ 无效{Style.RESET_ALL}"
            print(f"{Fore.CYAN}结果:{Style.RESET_ALL} {status}")
            
            if result.get("normalized"):
                print(f"  标准化: {result['normalized']}")
            if result.get("issues"):
                print(f"  问题: {', '.join(result['issues'])}")
            if result.get("suggestion"):
                print(f"  建议: {result['suggestion']}")
        else:
            print(f"{Fore.RED}错误:{Style.RESET_ALL} {result.get('error')}")
        
        print()
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 测试案例 2: 手机号验证
    print(f"{Fore.GREEN}案例 2: 手机号验证{Style.RESET_ALL}\n")
    
    test_phones = [
        "13812345678",                # 有效
        "138-1234-5678",              # 有效（带分隔符）
        "138 1234 5678",              # 有效（带空格）
        "12345",                      # 无效：长度不足
    ]
    
    for phone in test_phones:
        print(f"{Fore.YELLOW}输入:{Style.RESET_ALL} {phone}")
        result = validate_input(phone, "phone")
        
        if "error" not in result:
            status = f"{Fore.GREEN}✓ 有效{Style.RESET_ALL}" if result.get("valid") else f"{Fore.RED}✗ 无效{Style.RESET_ALL}"
            print(f"{Fore.CYAN}结果:{Style.RESET_ALL} {status}")
            
            if result.get("normalized"):
                print(f"  标准化: {result['normalized']}")
            if result.get("issues"):
                print(f"  问题: {', '.join(result['issues'])}")
            if result.get("suggestion"):
                print(f"  建议: {result['suggestion']}")
        else:
            print(f"{Fore.RED}错误:{Style.RESET_ALL} {result.get('error')}")
        
        print()
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 测试案例 3: SQL 注入检测
    print(f"{Fore.GREEN}案例 3: SQL 注入检测{Style.RESET_ALL}\n")
    
    test_sql_inputs = [
        "张三",                       # 安全
        "admin' OR '1'='1",          # SQL 注入
        "user; DROP TABLE users;",   # SQL 注入
        "normal_username",           # 安全
    ]
    
    for sql_input in test_sql_inputs:
        print(f"{Fore.YELLOW}输入:{Style.RESET_ALL} {sql_input}")
        result = validate_input(sql_input, "sql")
        
        if "error" not in result:
            status = f"{Fore.GREEN}✓ 安全{Style.RESET_ALL}" if result.get("safe") else f"{Fore.RED}✗ 危险{Style.RESET_ALL}"
            risk = result.get("risk_level", "unknown")
            print(f"{Fore.CYAN}结果:{Style.RESET_ALL} {status} (风险等级: {risk})")
            
            if result.get("threats"):
                print(f"  威胁: {', '.join(result['threats'])}")
            if result.get("suggestion"):
                print(f"  建议: {result['suggestion']}")
        else:
            print(f"{Fore.RED}错误:{Style.RESET_ALL} {result.get('error')}")
        
        print()
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 测试案例 4: XSS 攻击检测
    print(f"{Fore.GREEN}案例 4: XSS 攻击检测{Style.RESET_ALL}\n")
    
    test_xss_inputs = [
        "Hello World",                           # 安全
        "<script>alert('XSS')</script>",        # XSS 攻击
        "<img src=x onerror=alert('XSS')>",     # XSS 攻击
        "正常的文本内容",                         # 安全
    ]
    
    for xss_input in test_xss_inputs:
        print(f"{Fore.YELLOW}输入:{Style.RESET_ALL} {xss_input}")
        result = validate_input(xss_input, "xss")
        
        if "error" not in result:
            status = f"{Fore.GREEN}✓ 安全{Style.RESET_ALL}" if result.get("safe") else f"{Fore.RED}✗ 危险{Style.RESET_ALL}"
            risk = result.get("risk_level", "unknown")
            print(f"{Fore.CYAN}结果:{Style.RESET_ALL} {status} (风险等级: {risk})")
            
            if result.get("threats"):
                print(f"  威胁: {', '.join(result['threats'])}")
            if result.get("suggestion"):
                print(f"  建议: {result['suggestion']}")
        else:
            print(f"{Fore.RED}错误:{Style.RESET_ALL} {result.get('error')}")
        
        print()
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    # 总结
    print_section("技术总结")
    
    print(f"{Fore.GREEN}本案例使用的 Prompt Engineering 技术:{Style.RESET_ALL}\n")
    
    print("1. System Prompt:")
    print("   - 定义验证专家角色")
    print("   - 明确职责和原则")
    print("   - 设定安全优先的行为\n")
    
    print("2. Structured Output:")
    print("   - JSON 格式输出")
    print("   - 包含验证结果、问题、建议")
    print("   - 便于程序化处理\n")
    
    print("3. Few-shot Learning:")
    print("   - 提供正面和负面示例")
    print("   - 明确输出格式")
    print("   - 展示验证逻辑\n")
    
    print("4. 明确规则:")
    print("   - 具体的验证标准")
    print("   - 清晰的检查项")
    print("   - 标准化处理方式\n")
    
    print(f"{Fore.YELLOW}实际应用价值:{Style.RESET_ALL}\n")
    print("✓ 自动化输入验证")
    print("✓ 检测安全威胁（SQL注入、XSS）")
    print("✓ 标准化用户输入")
    print("✓ 提供友好的错误提示")
    print("✓ 减少人工审核工作\n")
    
    print(f"{Fore.YELLOW}注意事项:{Style.RESET_ALL}\n")
    print("⚠️  LLM 验证应作为辅助手段，不能完全替代传统验证")
    print("⚠️  关键安全检查仍需使用专门的安全库")
    print("⚠️  建议组合使用：LLM + 正则表达式 + 安全库")
    print("⚠️  对于高风险输入，采用白名单策略更安全\n")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}LLM 让输入验证更智能、更友好{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
