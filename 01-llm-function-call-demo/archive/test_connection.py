"""
测试 LLM 连接的独立脚本
用于验证 API 配置是否正确
"""

from llm_client import LLMClient
from colorama import Fore, Style, init

# 初始化 colorama
init(autoreset=True)


def main():
    print(f"\n{Fore.CYAN}{'='*70}")
    print("LLM 连接测试工具")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    
    print("正在读取 .env 配置文件...\n")
    
    try:
        # 初始化客户端
        client = LLMClient()
        
        print(f"\n{Fore.YELLOW}发送测试消息...{Style.RESET_ALL}\n")
        
        # 测试基本对话
        response = client.chat_completion(
            messages=[
                {"role": "user", "content": "你好！请用一句话介绍你自己。"}
            ],
            temperature=0.7
        )
        
        content = client.get_message_content(response)
        
        print(f"{Fore.GREEN}✓ 连接成功！{Style.RESET_ALL}\n")
        print(f"模型回复:\n{Fore.CYAN}{content}{Style.RESET_ALL}\n")
        
        print(f"{Fore.GREEN}{'='*70}")
        print("配置正确，可以开始使用 Function Call 功能了！")
        print(f"{'='*70}{Style.RESET_ALL}\n")
        
        print("下一步:")
        print("  运行 python openai_example.py 查看完整示例\n")
        
    except Exception as e:
        print(f"{Fore.RED}❌ 连接失败！{Style.RESET_ALL}\n")
        print(f"错误信息: {str(e)}\n")
        
        print(f"{Fore.YELLOW}请检查以下配置:{Style.RESET_ALL}")
        print("  1. .env 文件是否存在")
        print("  2. API_KEY 是否正确")
        print("  3. API_BASE_URL 是否正确")
        print("  4. MODEL_ID 是否正确")
        print("  5. 网络连接是否正常")
        print("\n配置示例:")
        print("  API_KEY=sk-xxx")
        print("  API_BASE_URL=https://api.openai.com/v1")
        print("  MODEL_ID=gpt-4-turbo-preview\n")


if __name__ == "__main__":
    main()
