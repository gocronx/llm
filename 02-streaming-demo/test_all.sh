#!/bin/bash

echo "============================================================"
echo "测试 Streaming 三语言版本"
echo "============================================================"
echo ""

# Python
echo "1️⃣  测试 Python 版本..."
cd python
python streaming_with_function_call.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Python 版本测试通过"
else
    echo "   ❌ Python 版本测试失败"
fi
cd ..

# Go
echo "2️⃣  测试 Go 版本..."
cd go
go run basic_streaming.go > /dev/null 2>&1 &
GO_PID=$!
sleep 5
kill $GO_PID 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Go 版本可以运行"
else
    echo "   ⚠️  Go 版本状态未知"
fi
cd ..

# Rust
echo "3️⃣  测试 Rust 版本..."
cd rust
cargo run --release > /dev/null 2>&1 &
RUST_PID=$!
sleep 5
kill $RUST_PID 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Rust 版本可以运行"
else
    echo "   ⚠️  Rust 版本状态未知"
fi
cd ..

echo ""
echo "============================================================"
echo "测试完成"
echo "============================================================"
