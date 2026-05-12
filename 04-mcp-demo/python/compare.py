"""
MCP vs Function Call 对比演示
"""

from colorama import Fore, Style, init

init(autoreset=True)


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("MCP vs Function Call 对比")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}1. 架构对比{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}Function Call (传统方式):{Style.RESET_ALL}\n")
    print("```")
    print("应用 A")
    print("  ├── 定义工具 1")
    print("  ├── 定义工具 2")
    print("  └── 实现工具逻辑")
    print("")
    print("应用 B")
    print("  ├── 重新定义工具 1  ❌ 重复")
    print("  ├── 重新定义工具 2  ❌ 重复")
    print("  └── 重新实现逻辑    ❌ 重复")
    print("```\n")
    
    print(f"{Fore.GREEN}MCP (标准化方式):{Style.RESET_ALL}\n")
    print("```")
    print("MCP Server (文件系统)")
    print("  ├── read_file")
    print("  ├── write_file")
    print("  └── list_directory")
    print("")
    print("应用 A  →  连接 MCP Server  ✅ 复用")
    print("应用 B  →  连接 MCP Server  ✅ 复用")
    print("应用 C  →  连接 MCP Server  ✅ 复用")
    print("```\n")
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}2. 工具定义对比{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}Function Call:{Style.RESET_ALL}\n")
    print("```python")
    print("# 每个应用自己定义")
    print("tools = [")
    print("    {")
    print('        "type": "function",')
    print('        "function": {')
    print('            "name": "read_file",')
    print('            "description": "读取文件",')
    print('            "parameters": {...}')
    print("        }")
    print("    }")
    print("]")
    print("```\n")
    
    print(f"{Fore.GREEN}MCP:{Style.RESET_ALL}\n")
    print("```python")
    print("# MCP Server 定义一次")
    print("@server.list_tools()")
    print("async def list_tools() -> List[Tool]:")
    print("    return [")
    print("        Tool(")
    print('            name="read_file",')
    print('            description="读取文件",')
    print("            inputSchema={...}")
    print("        )")
    print("    ]")
    print("")
    print("# 所有 Client 都可以使用")
    print("```\n")
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}3. 实际价值对比{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}Function Call:{Style.RESET_ALL}")
    print("  优点:")
    print("    ✅ 简单直接")
    print("    ✅ 灵活自由")
    print("  缺点:")
    print("    ❌ 没有标准")
    print("    ❌ 难以复用")
    print("    ❌ 生态碎片化\n")
    
    print(f"{Fore.GREEN}MCP:{Style.RESET_ALL}")
    print("  优点:")
    print("    ✅ 统一标准")
    print("    ✅ 易于复用")
    print("    ✅ 生态健康")
    print("    ✅ 长期价值高")
    print("  缺点:")
    print("    ⚠️  稍微复杂")
    print("    ⚠️  需要运行 Server\n")
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}4. 使用场景{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}适合 Function Call:{Style.RESET_ALL}")
    print("  - 简单的一次性工具")
    print("  - 应用特定的逻辑")
    print("  - 快速原型\n")
    
    print(f"{Fore.GREEN}适合 MCP:{Style.RESET_ALL}")
    print("  - 通用的工具（文件系统、数据库）")
    print("  - 需要在多个应用中复用")
    print("  - 生产环境\n")
    
    print(f"{Fore.CYAN}{'-'*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}5. 现有 MCP Servers{Style.RESET_ALL}\n")
    
    print("Anthropic 官方提供:")
    print("  📁 filesystem - 文件系统操作")
    print("  🗄️  sqlite - SQLite 数据库")
    print("  🌐 fetch - HTTP 请求")
    print("  🐙 github - GitHub API")
    print("  📊 google-drive - Google Drive")
    print("  🔍 brave-search - Brave 搜索\n")
    
    print("社区提供:")
    print("  🐘 postgresql - PostgreSQL")
    print("  🍃 mongodb - MongoDB")
    print("  📧 gmail - Gmail API")
    print("  📝 notion - Notion API")
    print("  ... 更多\n")
    
    print(f"{Fore.CYAN}{'='*60}")
    print("结论")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}MCP 是未来趋势:{Style.RESET_ALL}\n")
    print("1. Anthropic 大力推广")
    print("2. 统一标准，生态健康")
    print("3. 长期价值高")
    print("4. 但 Function Call 仍然有价值（简单场景）\n")
    
    print(f"{Fore.YELLOW}建议:{Style.RESET_ALL}\n")
    print("✓ 学习 Function Call（基础）")
    print("✓ 学习 MCP（进阶）")
    print("✓ 根据场景选择合适的方案\n")


if __name__ == "__main__":
    main()
