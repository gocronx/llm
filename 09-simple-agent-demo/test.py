"""
快速测试 Agent 是否正常工作
"""

from agent import SimpleAgent
from colorama import Fore, Style, init

init(autoreset=True)


def test_simple_task():
    """测试简单任务"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("测试 1: 简单任务（查询天气）")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    agent = SimpleAgent(max_iterations=5)
    result = agent.run("北京今天天气怎么样？", verbose=True)
    
    # 检查结果
    if "温度" in result or "天气" in result or "15" in result:
        print(f"{Fore.GREEN}✓ 测试通过{Style.RESET_ALL}\n")
        return True
    else:
        print(f"{Fore.RED}✗ 测试失败{Style.RESET_ALL}\n")
        return False


def test_calculation():
    """测试计算任务"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("测试 2: 计算任务")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    agent = SimpleAgent(max_iterations=5)
    result = agent.run("计算 156 除以 12", verbose=True)
    
    # 检查结果
    if "13" in result:
        print(f"{Fore.GREEN}✓ 测试通过{Style.RESET_ALL}\n")
        return True
    else:
        print(f"{Fore.RED}✗ 测试失败{Style.RESET_ALL}\n")
        return False


def test_search():
    """测试搜索任务"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("测试 3: 搜索任务")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    agent = SimpleAgent(max_iterations=5)
    result = agent.run("搜索手机产品", verbose=True)
    
    # 检查结果
    if "iPhone" in result or "手机" in result:
        print(f"{Fore.GREEN}✓ 测试通过{Style.RESET_ALL}\n")
        return True
    else:
        print(f"{Fore.RED}✗ 测试失败{Style.RESET_ALL}\n")
        return False


def main():
    print(f"\n{Fore.CYAN}{'='*60}")
    print("Agent 功能测试")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    results = []
    
    # 测试 1: 简单任务
    try:
        results.append(("查询天气", test_simple_task()))
    except Exception as e:
        print(f"{Fore.RED}测试 1 异常: {e}{Style.RESET_ALL}\n")
        results.append(("查询天气", False))
    
    # 测试 2: 计算
    try:
        results.append(("计算", test_calculation()))
    except Exception as e:
        print(f"{Fore.RED}测试 2 异常: {e}{Style.RESET_ALL}\n")
        results.append(("计算", False))
    
    # 测试 3: 搜索
    try:
        results.append(("搜索", test_search()))
    except Exception as e:
        print(f"{Fore.RED}测试 3 异常: {e}{Style.RESET_ALL}\n")
        results.append(("搜索", False))
    
    # 总结
    print(f"\n{Fore.CYAN}{'='*60}")
    print("测试结果")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{Fore.GREEN}✓ 通过{Style.RESET_ALL}" if result else f"{Fore.RED}✗ 失败{Style.RESET_ALL}"
        print(f"{name}: {status}")
    
    print(f"\n{Fore.CYAN}总计: {passed}/{total} 通过{Style.RESET_ALL}\n")
    
    if passed == total:
        print(f"{Fore.GREEN}{'='*60}")
        print("所有测试通过！Agent 工作正常。")
        print(f"{'='*60}{Style.RESET_ALL}\n")
    else:
        print(f"{Fore.YELLOW}{'='*60}")
        print(f"部分测试失败，请检查 API 配置和网络连接。")
        print(f"{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
