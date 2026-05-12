"""
模型对比：哪些支持 Function Call，为什么？
"""

from colorama import Fore, Style, init

init(autoreset=True)

print(f"\n{Fore.CYAN}{'='*70}")
print("LLM 模型 Function Call 支持情况对比")
print(f"{'='*70}{Style.RESET_ALL}\n")


# ============================================================
# 支持 Function Call 的模型
# ============================================================

print(f"{Fore.GREEN}✅ 支持 Function Call 的模型{Style.RESET_ALL}\n")

supported_models = [
    {
        "name": "OpenAI GPT-4 / GPT-4 Turbo",
        "company": "OpenAI",
        "size": "未公开（估计 >1T）",
        "type": "商业闭源",
        "reason": "商业产品，重点功能，投入大量资源训练",
        "quality": "⭐⭐⭐⭐⭐"
    },
    {
        "name": "OpenAI GPT-3.5 Turbo",
        "company": "OpenAI",
        "size": "未公开",
        "type": "商业闭源",
        "reason": "商业产品，成本较低的选择",
        "quality": "⭐⭐⭐⭐"
    },
    {
        "name": "Claude 3 (Opus/Sonnet/Haiku)",
        "company": "Anthropic",
        "size": "未公开",
        "type": "商业闭源",
        "reason": "商业产品，强调工具使用能力",
        "quality": "⭐⭐⭐⭐⭐"
    },
    {
        "name": "智谱 GLM-4",
        "company": "智谱 AI",
        "size": "未公开",
        "type": "商业闭源",
        "reason": "针对企业市场，重点功能",
        "quality": "⭐⭐⭐⭐"
    },
    {
        "name": "通义千问 Turbo/Plus/Max",
        "company": "阿里云",
        "size": "72B+",
        "type": "商业闭源",
        "reason": "企业级产品，集成阿里生态",
        "quality": "⭐⭐⭐⭐"
    },
    {
        "name": "DeepSeek Chat",
        "company": "DeepSeek",
        "size": "67B",
        "type": "商业闭源",
        "reason": "技术导向公司，完整功能",
        "quality": "⭐⭐⭐⭐"
    },
    {
        "name": "Google Gemini Pro",
        "company": "Google",
        "size": "未公开",
        "type": "商业闭源",
        "reason": "Google 的旗舰产品",
        "quality": "⭐⭐⭐⭐"
    }
]

for i, model in enumerate(supported_models, 1):
    print(f"{i}. {Fore.YELLOW}{model['name']}{Style.RESET_ALL}")
    print(f"   公司: {model['company']}")
    print(f"   规模: {model['size']}")
    print(f"   类型: {model['type']}")
    print(f"   质量: {model['quality']}")
    print(f"   原因: {model['reason']}\n")


# ============================================================
# 不支持 Function Call 的模型
# ============================================================

print(f"\n{Fore.RED}❌ 不支持 Function Call 的模型{Style.RESET_ALL}\n")

unsupported_models = [
    {
        "name": "Llama 2",
        "company": "Meta",
        "size": "7B / 13B / 70B",
        "type": "开源",
        "reason": "基础模型，未专门训练 Function Call",
        "alternative": "可以微调添加支持"
    },
    {
        "name": "Mistral 7B",
        "company": "Mistral AI",
        "size": "7B",
        "type": "开源",
        "reason": "轻量级模型，专注基础能力",
        "alternative": "使用 Mistral Large（商业版）"
    },
    {
        "name": "Vicuna",
        "company": "LMSYS",
        "size": "7B / 13B",
        "type": "开源",
        "reason": "基于 Llama 微调，未加入 Function Call",
        "alternative": "使用其他微调版本"
    },
    {
        "name": "ChatGLM2-6B",
        "company": "智谱 AI",
        "size": "6B",
        "type": "开源",
        "reason": "轻量级版本，能力有限",
        "alternative": "使用 GLM-4（商业版）"
    },
    {
        "name": "Qwen-7B",
        "company": "阿里云",
        "size": "7B",
        "type": "开源",
        "reason": "基础开源版本",
        "alternative": "使用通义千问（商业版）"
    },
    {
        "name": "LongCat-Flash-Lite",
        "company": "美团",
        "size": "未知",
        "type": "商业",
        "reason": "轻量级模型，专注对话",
        "alternative": "使用其他美团模型或切换提供商"
    }
]

for i, model in enumerate(unsupported_models, 1):
    print(f"{i}. {Fore.YELLOW}{model['name']}{Style.RESET_ALL}")
    print(f"   公司: {model['company']}")
    print(f"   规模: {model['size']}")
    print(f"   类型: {model['type']}")
    print(f"   原因: {model['reason']}")
    print(f"   替代: {model['alternative']}\n")


# ============================================================
# 关键差异分析
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("关键差异分析")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}1. 商业 vs 开源{Style.RESET_ALL}\n")
print("商业模型（大多支持）：")
print("  ✓ 有资金投入专门训练")
print("  ✓ 针对企业需求设计")
print("  ✓ 持续优化和更新\n")

print("开源模型（大多不支持）：")
print("  ✗ 资源有限")
print("  ✗ 专注基础能力")
print("  ✗ 需要社区贡献\n")

print(f"{Fore.YELLOW}2. 模型规模{Style.RESET_ALL}\n")
print("大模型（>30B）：")
print("  ✓ 能力强，可以处理复杂任务")
print("  ✓ 更容易训练 Function Call\n")

print("小模型（<10B）：")
print("  ✗ 能力有限")
print("  ✗ 难以同时处理多个任务\n")

print(f"{Fore.YELLOW}3. 训练目标{Style.RESET_ALL}\n")
print("通用助手（支持）：")
print("  ✓ 需要调用外部工具")
print("  ✓ Function Call 是核心功能\n")

print("专用模型（不支持）：")
print("  ✗ 只需要特定能力（如翻译、代码补全）")
print("  ✗ 不需要 Function Call\n")


# ============================================================
# 训练成本对比
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("训练成本对比")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.GREEN}基础 LLM 训练：{Style.RESET_ALL}")
print("  • 数据：通用文本语料")
print("  • 时间：数周到数月")
print("  • 成本：数百万到数千万美元")
print("  • 结果：能对话，能理解，能生成\n")

print(f"{Fore.YELLOW}添加 Function Call 能力：{Style.RESET_ALL}")
print("  • 额外数据：函数调用示例数据集")
print("  • 额外时间：数周")
print("  • 额外成本：+20-30%")
print("  • 额外复杂度：需要精心设计训练数据")
print("  • 结果：能对话 + 能调用函数\n")

print(f"{Fore.RED}为什么小公司/开源项目不做？{Style.RESET_ALL}")
print("  ✗ 成本太高")
print("  ✗ 需要专业知识")
print("  ✗ 数据难以获取")
print("  ✗ 不是所有用户都需要\n")


# ============================================================
# 如何选择模型
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("如何选择模型？")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.GREEN}如果你需要 Function Call：{Style.RESET_ALL}\n")

print("1️⃣  预算充足 → OpenAI GPT-4")
print("   • 最佳效果")
print("   • 最稳定")
print("   • 最贵\n")

print("2️⃣  预算有限 → GPT-3.5 Turbo / 智谱 GLM-4")
print("   • 性价比高")
print("   • 效果不错")
print("   • 价格适中\n")

print("3️⃣  国内部署 → 智谱 GLM-4 / 通义千问")
print("   • 国内服务器")
print("   • 响应快")
print("   • 合规\n")

print("4️⃣  开源需求 → 微调 Llama 2 / 使用 Gorilla")
print("   • 完全控制")
print("   • 可以定制")
print("   • 需要技术能力\n")

print(f"{Fore.RED}如果你的模型不支持：{Style.RESET_ALL}\n")

print("方案 1: 切换到支持的模型（推荐）")
print("方案 2: 使用 Prompt Engineering 模拟（效果有限）")
print("方案 3: 等待模型更新")
print("方案 4: 自己微调模型（需要技术和资源）\n")


# ============================================================
# 未来趋势
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("未来趋势")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}📈 Function Call 会越来越普及{Style.RESET_ALL}\n")

print("现在（2024）：")
print("  • 主要是商业大模型支持")
print("  • 开源模型少数支持")
print("  • 需要专门选择\n")

print("未来（2025+）：")
print("  • 大部分商业模型都支持")
print("  • 越来越多开源模型支持")
print("  • 成为 LLM 的'标配'功能")
print("  • 训练成本降低")
print("  • 开源数据集增加\n")


# ============================================================
# 总结
# ============================================================

print(f"\n{Fore.CYAN}{'='*70}")
print("总结")
print(f"{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}为什么一些模型没有 Function Call？{Style.RESET_ALL}\n")

print("1. 需要专门训练 - 不是天生能力")
print("2. 成本高 - 需要额外的数据和计算")
print("3. 不是所有场景都需要 - 有些模型不需要这个功能")
print("4. 技术难度大 - 需要多种能力的结合")
print("5. 模型规模限制 - 小模型能力不足\n")

print(f"{Fore.GREEN}关键要点：{Style.RESET_ALL}\n")

print("✓ Function Call 是高级功能，需要专门训练")
print("✓ 商业大模型大多支持，开源小模型大多不支持")
print("✓ 如果需要这个功能，选择明确支持的模型")
print("✓ 未来会越来越普及\n")

print(f"{Fore.CYAN}💡 建议：{Style.RESET_ALL}")
print("查看 why_no_function_call.md 了解更多详情\n")
