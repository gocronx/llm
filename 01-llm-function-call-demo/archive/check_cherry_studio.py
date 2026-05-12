"""
检查 Cherry Studio 配置和可用模型
"""

import requests
import json
import os
from colorama import Fore, Style, init
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化 colorama
init(autoreset=True)


def check_cherry_studio():
    """检查 Cherry Studio 的 API 服务"""
    
    print(f"\n{Fore.CYAN}{'='*70}")
    print("Cherry Studio 配置检查工具")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    
    # 从环境变量读取配置
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:23333/v1").rstrip("/v1")
    api_key = os.getenv("API_KEY", "")
    
    print(f"正在检查 Cherry Studio 服务: {base_url}\n")
    
    # 准备请求头
    headers = {}
    if api_key and api_key != "not-needed":
        headers["Authorization"] = f"Bearer {api_key}"
        print(f"{Fore.GREEN}✓ 使用 API Key 认证{Style.RESET_ALL}\n")
    
    # 1. 检查服务是否运行并获取模型列表
    try:
        response = requests.get(f"{base_url}/v1/models", headers=headers, timeout=5)
        
        if response.status_code == 200:
            print(f"{Fore.GREEN}✓ Cherry Studio API 服务运行正常{Style.RESET_ALL}\n")
            
            # 2. 获取可用模型列表
            try:
                models_data = response.json()
                
                if "data" in models_data:
                    models = models_data["data"]
                    print(f"{Fore.CYAN}可用的模型列表：{Style.RESET_ALL}\n")
                    
                    for i, model in enumerate(models, 1):
                        model_id = model.get("id", "unknown")
                        print(f"  {i}. {Fore.YELLOW}{model_id}{Style.RESET_ALL}")
                    
                    if models:
                        recommended_model = models[0].get("id", "gpt-4")
                        
                        print(f"\n{Fore.GREEN}{'='*70}")
                        print("当前 .env 配置")
                        print(f"{'='*70}{Style.RESET_ALL}\n")
                        
                        print(f"MODEL_PROVIDER=custom")
                        print(f"API_KEY={api_key if api_key else 'not-needed'}")
                        print(f"API_BASE_URL={base_url}/v1")
                        print(f"MODEL_ID={os.getenv('MODEL_ID', recommended_model)}\n")
                        
                        # 3. 测试模型调用
                        print(f"{Fore.YELLOW}正在测试模型调用...{Style.RESET_ALL}\n")
                        test_model(base_url, os.getenv('MODEL_ID', recommended_model), api_key)
                    else:
                        print(f"\n{Fore.YELLOW}⚠️  未找到可用模型{Style.RESET_ALL}")
                        print("请在 Cherry Studio 中配置至少一个模型\n")
                        
            except json.JSONDecodeError:
                print(f"{Fore.RED}❌ 无法解析模型列表{Style.RESET_ALL}\n")
        
        elif response.status_code == 401:
            print(f"{Fore.RED}❌ 认证失败 (401 Unauthorized){Style.RESET_ALL}\n")
            print("Cherry Studio 需要 API Key 认证。请按以下步骤操作：\n")
            print("1. 打开 Cherry Studio")
            print("2. 进入 设置 → API 服务")
            print("3. 复制 API Key")
            print("4. 将 API Key 填入 .env 文件：\n")
            print(f"{Fore.CYAN}   API_KEY=your-cherry-studio-api-key{Style.RESET_ALL}\n")
        
        else:
            print(f"{Fore.RED}❌ API 返回错误状态码: {response.status_code}{Style.RESET_ALL}\n")
            print(f"响应内容: {response.text}\n")
    
    except requests.exceptions.ConnectionError:
        print(f"{Fore.RED}❌ 无法连接到 Cherry Studio{Style.RESET_ALL}\n")
        print("请检查：")
        print("  1. Cherry Studio 是否已启动")
        print("  2. API 服务是否已开启")
        print("  3. 端口是否正确（当前检查: 23333）\n")
        
        print(f"{Fore.YELLOW}如何启动 Cherry Studio 的 API 服务：{Style.RESET_ALL}")
        print("  1. 打开 Cherry Studio")
        print("  2. 进入 设置 (Settings)")
        print("  3. 找到 API 服务 或 本地服务器")
        print("  4. 启用 API 服务\n")
    
    except Exception as e:
        print(f"{Fore.RED}❌ 检查失败: {str(e)}{Style.RESET_ALL}\n")


def test_model(base_url: str, model_id: str, api_key: str = None):
    """测试模型调用"""
    
    headers = {}
    if api_key and api_key != "not-needed":
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": model_id,
                "messages": [
                    {"role": "user", "content": "你好，请用一句话介绍你自己"}
                ],
                "max_tokens": 100
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            print(f"{Fore.GREEN}✓ 模型调用成功{Style.RESET_ALL}")
            print(f"\n模型回复:\n{Fore.CYAN}{content}{Style.RESET_ALL}\n")
            
            print(f"{Fore.GREEN}{'='*70}")
            print("一切就绪！现在可以运行 Function Call 示例了")
            print(f"{'='*70}{Style.RESET_ALL}\n")
            
            print("运行以下命令开始：")
            print(f"  {Fore.YELLOW}python openai_example.py{Style.RESET_ALL}\n")
            
        else:
            print(f"{Fore.RED}❌ 模型调用失败: {response.status_code}{Style.RESET_ALL}")
            print(f"响应: {response.text}\n")
    
    except Exception as e:
        print(f"{Fore.RED}❌ 模型测试失败: {str(e)}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    check_cherry_studio()
