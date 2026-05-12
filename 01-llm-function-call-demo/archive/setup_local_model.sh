#!/bin/bash

# 本地模型快速安装脚本
# 适用于 MacBook Max 64GB

echo "=================================="
echo "本地 Function Call 模型安装向导"
echo "=================================="
echo ""

# 检查是否安装了 Ollama
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama 未安装"
    echo ""
    echo "请选择安装方式："
    echo "1. 使用 Homebrew 安装（推荐）"
    echo "2. 从官网下载安装"
    echo ""
    read -p "请选择 (1/2): " choice
    
    if [ "$choice" = "1" ]; then
        echo ""
        echo "正在使用 Homebrew 安装 Ollama..."
        brew install ollama
    else
        echo ""
        echo "请访问 https://ollama.ai/download 下载安装"
        echo "安装完成后重新运行此脚本"
        exit 1
    fi
fi

echo ""
echo "✓ Ollama 已安装"
echo ""

# 选择模型
echo "请选择要安装的模型："
echo ""
echo "1. Hermes-2-Pro-7B (推荐新手)"
echo "   - 参数: 7B"
echo "   - 内存: 8GB"
echo "   - 速度: 快"
echo "   - Function Call: ⭐⭐⭐⭐⭐"
echo ""
echo "2. Functionary-70B (推荐你的配置)"
echo "   - 参数: 70B"
echo "   - 内存: 45GB"
echo "   - 速度: 中"
echo "   - Function Call: ⭐⭐⭐⭐⭐"
echo ""
echo "3. Llama-3.1-8B (官方支持)"
echo "   - 参数: 8B"
echo "   - 内存: 10GB"
echo "   - 速度: 快"
echo "   - Function Call: ⭐⭐⭐⭐"
echo ""
echo "4. Llama-3.1-70B (官方大模型)"
echo "   - 参数: 70B"
echo "   - 内存: 45GB"
echo "   - 速度: 中"
echo "   - Function Call: ⭐⭐⭐⭐"
echo ""
echo "5. 全部安装（需要时间）"
echo ""

read -p "请选择 (1-5): " model_choice

case $model_choice in
    1)
        echo ""
        echo "正在下载 Hermes-2-Pro-7B..."
        ollama pull adrienbrault/nous-hermes2pro:Q8_0
        MODEL_ID="adrienbrault/nous-hermes2pro:Q8_0"
        ;;
    2)
        echo ""
        echo "正在下载 Functionary-70B（大文件，需要时间）..."
        ollama pull meetkai/functionary-large-v2.5
        MODEL_ID="meetkai/functionary-large-v2.5"
        ;;
    3)
        echo ""
        echo "正在下载 Llama-3.1-8B..."
        ollama pull llama3.1:8b
        MODEL_ID="llama3.1:8b"
        ;;
    4)
        echo ""
        echo "正在下载 Llama-3.1-70B（大文件，需要时间）..."
        ollama pull llama3.1:70b
        MODEL_ID="llama3.1:70b"
        ;;
    5)
        echo ""
        echo "正在下载所有模型（这需要很长时间）..."
        ollama pull adrienbrault/nous-hermes2pro:Q8_0
        ollama pull meetkai/functionary-large-v2.5
        ollama pull llama3.1:8b
        ollama pull llama3.1:70b
        MODEL_ID="adrienbrault/nous-hermes2pro:Q8_0"
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo "✓ 模型下载完成"
echo ""

# 更新 .env 文件
echo "正在更新配置文件..."

cat > .env << EOF
# ============================================
# LLM API 配置 - 本地 Ollama
# ============================================

# 本地模型配置
MODEL_PROVIDER=custom
API_KEY=not-needed
API_BASE_URL=http://localhost:11434/v1
MODEL_ID=$MODEL_ID

# 说明：
# - 使用本地 Ollama 运行的模型
# - 无需 API Key
# - 完全本地运行，隐私安全
EOF

echo "✓ 配置文件已更新"
echo ""

# 启动 Ollama 服务
echo "正在启动 Ollama 服务..."
echo ""
echo "请在新终端窗口运行: ollama serve"
echo "或者让它在后台运行"
echo ""

read -p "是否现在启动 Ollama 服务？(y/n): " start_service

if [ "$start_service" = "y" ] || [ "$start_service" = "Y" ]; then
    echo ""
    echo "正在后台启动 Ollama..."
    nohup ollama serve > ollama.log 2>&1 &
    sleep 3
    echo "✓ Ollama 已启动"
fi

echo ""
echo "=================================="
echo "安装完成！"
echo "=================================="
echo ""
echo "下一步："
echo "1. 测试连接: python test_connection.py"
echo "2. 运行示例: python openai_example.py"
echo ""
echo "模型信息："
echo "  模型: $MODEL_ID"
echo "  API: http://localhost:11434/v1"
echo ""
echo "如需切换模型，编辑 .env 文件中的 MODEL_ID"
echo ""
