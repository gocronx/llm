"""
混合检索交互式演示
结合 GREP + 向量检索 + LLM 长上下文
"""

import os
import requests
from dotenv import load_dotenv
from search import HybridSearch
from colorama import Fore, Style, init

# 初始化
init(autoreset=True)
load_dotenv()

# 配置
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def call_llm(context: str, question: str) -> str:
    """调用 LLM 生成答案"""
    # 限制上下文长度，避免超时
    max_context_length = 3000
    if len(context) > max_context_length:
        context = context[:max_context_length] + "\n\n... (内容过长，已截断)"
    
    prompt = f"""你是一个代码助手。基于以下代码片段回答用户的问题。

代码片段:
{context}

用户问题: {question}

请简洁回答（200字以内）：
1. 直接回答问题
2. 引用关键代码
"""
    
    try:
        print(f"{Fore.CYAN}→ 正在调用 LLM (超时30秒)...{Style.RESET_ALL}")
        
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,  # 减少 token 数
                "temperature": 0.7
            },
            timeout=30  # 减少超时时间
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"API 错误 {response.status_code}: {response.text[:200]}"
    except requests.Timeout:
        return "⚠️ API 调用超时（30秒），请检查模型服务是否正常运行"
    except requests.ConnectionError:
        return "⚠️ 无法连接到 API，请检查 API_BASE_URL 配置"
    except Exception as e:
        return f"⚠️ 调用 LLM 失败: {type(e).__name__}: {str(e)}"


def format_search_results(results):
    """格式化搜索结果"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"找到 {len(results)} 个相关结果")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    for i, result in enumerate(results, 1):
        print(f"{Fore.GREEN}{i}. {result.file_path}{Style.RESET_ALL}")
        print(f"   {Fore.YELLOW}综合分数: {result.score:.3f}{Style.RESET_ALL} ", end="")
        print(f"(GREP: {result.grep_score:.2f}, Vector: {result.vector_score:.3f})")
        
        # 显示代码片段
        content_preview = result.content[:200].replace('\n', '\n   ')
        print(f"   {content_preview}...")
        print()


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("混合检索系统 Demo")
    print("GREP + 向量检索 + LLM 长上下文")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 初始化搜索器
    print("正在加载索引...")
    searcher = HybridSearch("sample_code")
    
    try:
        searcher.load_index()
        print(f"{Fore.GREEN}✓ 索引加载成功{Style.RESET_ALL}\n")
    except FileNotFoundError:
        print(f"{Fore.YELLOW}索引不存在，正在构建...{Style.RESET_ALL}")
        searcher.build_index()
        print(f"{Fore.GREEN}✓ 索引构建完成{Style.RESET_ALL}\n")
    
    # 显示统计信息
    stats = searcher.get_stats()
    print(f"索引统计: {stats['vector']}\n")
    
    # 交互式搜索
    print(f"{Fore.CYAN}输入查询开始搜索（输入 'quit' 退出）{Style.RESET_ALL}\n")
    
    while True:
        try:
            query = input(f"{Fore.YELLOW}🔍 查询: {Style.RESET_ALL}").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print(f"\n{Fore.CYAN}再见！{Style.RESET_ALL}")
                break
            
            # 执行混合搜索
            print(f"\n{Fore.CYAN}正在搜索...{Style.RESET_ALL}")
            results = searcher.search(query, top_k=5)
            
            if not results:
                print(f"{Fore.RED}未找到相关结果{Style.RESET_ALL}\n")
                continue
            
            # 显示搜索结果
            format_search_results(results)
            
            # 询问是否使用 LLM 生成答案
            use_llm = input(f"{Fore.YELLOW}是否使用 LLM 生成答案？(y/n): {Style.RESET_ALL}").strip().lower()
            
            if use_llm == 'y':
                print(f"\n{Fore.CYAN}→ 准备上下文...{Style.RESET_ALL}")
                
                # 合并上下文（限制每个结果的长度）
                try:
                    context_parts = []
                    for r in results[:3]:  # 只使用前3个结果
                        # 限制每个片段最多1000字符
                        content = r.content[:1000] if len(r.content) > 1000 else r.content
                        context_parts.append(f"# 文件: {r.file_path}\n{content}")
                    
                    context = "\n\n".join(context_parts)
                    print(f"{Fore.CYAN}→ 上下文长度: {len(context)} 字符{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}✗ 合并上下文失败: {e}{Style.RESET_ALL}\n")
                    continue
                
                answer = call_llm(context, query)
                
                print(f"\n{Fore.GREEN}{'='*60}")
                print("LLM 回答:")
                print(f"{'='*60}{Style.RESET_ALL}\n")
                print(answer)
            
            print(f"\n{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
            
        except KeyboardInterrupt:
            print(f"\n\n{Fore.CYAN}再见！{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"{Fore.RED}错误: {e}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
