"""
快速测试脚本（不使用 LLM）
"""

from search import HybridSearch
from colorama import Fore, Style, init

init(autoreset=True)


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("混合检索快速测试（无 LLM）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 初始化
    searcher = HybridSearch("sample_code")
    
    try:
        searcher.load_index()
        print(f"{Fore.GREEN}✓ 索引加载成功{Style.RESET_ALL}\n")
    except FileNotFoundError:
        print("正在构建索引...")
        searcher.build_index()
    
    # 测试查询
    test_queries = [
        "用户认证",
        "数据库连接",
        "API 路由",
        "密码验证",
        "JWT token"
    ]
    
    for query in test_queries:
        print(f"{Fore.YELLOW}查询: {query}{Style.RESET_ALL}")
        
        results = searcher.search(query, top_k=3)
        
        if results:
            for i, r in enumerate(results, 1):
                print(f"  {i}. {Fore.GREEN}{r.file_path}{Style.RESET_ALL}")
                print(f"     分数: {r.score:.3f} (GREP: {r.grep_score:.2f}, Vector: {r.vector_score:.3f})")
        else:
            print(f"  {Fore.RED}未找到结果{Style.RESET_ALL}")
        
        print()
    
    print(f"{Fore.CYAN}{'='*60}")
    print("测试完成！")
    print(f"{'='*60}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
