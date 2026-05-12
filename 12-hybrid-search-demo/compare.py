"""
对比不同检索策略的效果
"""

from search import HybridSearch
from colorama import Fore, Style, init

init(autoreset=True)


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("检索策略对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # 初始化搜索器
    searcher = HybridSearch("sample_code")
    
    try:
        searcher.load_index()
    except FileNotFoundError:
        print("正在构建索引...")
        searcher.build_index()
    
    # 测试查询（使用简单关键词）
    test_queries = [
        "认证",
        "登录",
        "数据库",
        "连接池",
        "API",
        "路由",
        "密码",
        "哈希",
    ]
    
    strategies = {
        "grep_only": "仅 GREP（精确匹配）",
        "vector_only": "仅向量（语义搜索）",
        "balanced": "平衡策略（GREP 40% + Vector 60%）",
        "precise": "精确策略（GREP 70% + Vector 30%）",
        "semantic": "语义策略（GREP 20% + Vector 80%）"
    }
    
    for query in test_queries:
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"查询: {query}")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        for strategy_name, strategy_desc in strategies.items():
            print(f"{Fore.GREEN}【{strategy_desc}】{Style.RESET_ALL}")
            
            results = searcher.search_with_strategy(query, top_k=3, strategy=strategy_name)
            
            if not results:
                print(f"  {Fore.RED}未找到结果{Style.RESET_ALL}\n")
                continue
            
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.file_path}")
                print(f"     分数: {r.score:.3f} (GREP: {r.grep_score:.2f}, Vector: {r.vector_score:.3f})")
            
            print()
        
        print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}")
    
    # 总结
    print(f"\n{Fore.CYAN}{'='*60}")
    print("总结")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}✓ GREP 搜索{Style.RESET_ALL}")
    print("  优势: 精确匹配关键词，速度快，小代码库完全够用")
    print("  劣势: 无法理解同义词和语义")
    print(f"  {Fore.YELLOW}本案例表现: ⭐⭐⭐⭐⭐ (完美){Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}✓ 向量搜索（TF-IDF 字符级）{Style.RESET_ALL}")
    print("  优势: 理论上能理解语义")
    print("  劣势: 中文效果差，需要真正的 Embedding")
    print(f"  {Fore.YELLOW}本案例表现: ⭐⭐ (较弱，分数 0.04-0.13){Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}✓ 混合检索{Style.RESET_ALL}")
    print("  优势: 结合两者优点（理论上）")
    print("  劣势: 在小代码库中，向量贡献小，反而降低分数")
    print(f"  {Fore.YELLOW}本案例表现: ⭐⭐⭐ (不如纯 GREP){Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}{'='*60}")
    print("实际建议")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}小型项目（<50 文件）：{Style.RESET_ALL}")
    print("  → 直接用 GREP，简单高效\n")
    
    print(f"{Fore.YELLOW}中型项目（50-500 文件）：{Style.RESET_ALL}")
    print("  → GREP + 长上下文 LLM\n")
    
    print(f"{Fore.YELLOW}大型项目（>500 文件）：{Style.RESET_ALL}")
    print("  → 混合检索（需要好的 Embedding，如 OpenAI）\n")
    
    print(f"{Fore.GREEN}核心教训：{Style.RESET_ALL}")
    print("  选择合适的工具，而不是最复杂的工具。")


if __name__ == "__main__":
    main()
