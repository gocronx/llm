"""
实战案例：软件开发团队
模拟一个完整的软件开发流程
"""

import os
import json
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
from colorama import Fore, Style, init
from multi_agent import Agent, MultiAgentOrchestrator

init(autoreset=True)
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")


def create_software_team():
    """创建软件开发团队"""
    
    orchestrator = MultiAgentOrchestrator()
    
    # 1. 产品经理
    pm = Agent(
        name="ProductManager",
        role="产品经理，负责需求分析和功能设计"
    )
    orchestrator.register_agent(pm)
    
    # 2. 架构师
    architect = Agent(
        name="Architect",
        role="系统架构师，负责技术方案设计"
    )
    orchestrator.register_agent(architect)
    
    # 3. 后端工程师
    backend_dev = Agent(
        name="BackendDev",
        role="后端工程师，负责 API 开发"
    )
    orchestrator.register_agent(backend_dev)
    
    # 4. 前端工程师
    frontend_dev = Agent(
        name="FrontendDev",
        role="前端工程师，负责 UI 开发"
    )
    orchestrator.register_agent(frontend_dev)
    
    # 5. 测试工程师
    qa = Agent(
        name="QA",
        role="测试工程师，负责测试用例设计和质量保证"
    )
    orchestrator.register_agent(qa)
    
    # 6. DevOps 工程师
    devops = Agent(
        name="DevOps",
        role="DevOps 工程师，负责部署和运维"
    )
    orchestrator.register_agent(devops)
    
    return orchestrator


def main():
    print(f"{Fore.CYAN}{'='*60}")
    print("实战案例：软件开发团队协作")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.GREEN}项目:{Style.RESET_ALL} 开发一个用户注册登录系统\n")
    
    # 创建团队
    team = create_software_team()
    
    print()
    
    # 定义开发流程
    workflow = [
        {
            "id": "requirements",
            "agent": "ProductManager",
            "task": "分析用户注册登录系统的需求，列出核心功能"
        },
        {
            "id": "architecture",
            "agent": "Architect",
            "task": "基于需求设计系统架构，包括技术栈选择、数据库设计、API 设计",
            "depends_on": ["requirements"]
        },
        {
            "id": "backend",
            "agent": "BackendDev",
            "task": "实现用户注册和登录的后端 API（Python + FastAPI）",
            "depends_on": ["architecture"]
        },
        {
            "id": "frontend",
            "agent": "FrontendDev",
            "task": "实现用户注册和登录的前端页面（React）",
            "depends_on": ["architecture"]
        },
        {
            "id": "testing",
            "agent": "QA",
            "task": "设计测试用例，包括功能测试、安全测试、性能测试",
            "depends_on": ["backend", "frontend"]
        },
        {
            "id": "deployment",
            "agent": "DevOps",
            "task": "设计部署方案，包括 Docker 配置、CI/CD 流程",
            "depends_on": ["backend", "frontend", "testing"]
        }
    ]
    
    # 执行工作流
    results = team.execute_workflow(workflow)
    
    # 显示最终交付物
    print(f"{Fore.GREEN}{'='*60}")
    print("项目交付物")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    deliverables = {
        "requirements": "需求文档",
        "architecture": "架构设计",
        "backend": "后端代码",
        "frontend": "前端代码",
        "testing": "测试用例",
        "deployment": "部署方案"
    }
    
    for step_id, title in deliverables.items():
        if step_id in results and results[step_id]["success"]:
            print(f"{Fore.CYAN}📄 {title}{Style.RESET_ALL}")
            result_text = results[step_id]["result"]
            # 显示前 300 字符
            preview = result_text[:300] + "..." if len(result_text) > 300 else result_text
            print(f"{preview}\n")
    
    # 统计
    print(f"{Fore.CYAN}{'='*60}")
    print("项目统计")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    total_steps = len(workflow)
    success_steps = sum(1 for r in results.values() if r.get("success"))
    
    print(f"总步骤: {total_steps}")
    print(f"成功: {success_steps}")
    print(f"成功率: {success_steps/total_steps*100:.1f}%\n")
    
    # Multi-Agent 的优势
    print(f"{Fore.CYAN}{'='*60}")
    print("Multi-Agent 在软件开发中的优势")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}传统方式:{Style.RESET_ALL}")
    print("  - 一个 AI 完成所有任务")
    print("  - 容易遗漏细节")
    print("  - 质量不稳定\n")
    
    print(f"{Fore.YELLOW}Multi-Agent 方式:{Style.RESET_ALL}")
    print("  ✓ 专业分工（PM、架构师、开发、测试、运维）")
    print("  ✓ 每个角色专注自己的领域")
    print("  ✓ 互相审查，提高质量")
    print("  ✓ 流程清晰，可追溯\n")
    
    print(f"{Fore.GREEN}实际应用:{Style.RESET_ALL}")
    print("  - 自动化代码生成")
    print("  - 自动化测试")
    print("  - 自动化文档生成")
    print("  - 自动化部署\n")


if __name__ == "__main__":
    main()
