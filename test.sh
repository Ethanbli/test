#!/bin/bash

echo "========== 开始网站自动测试 =========="

# 测试1：index.html 是否存在
if [ ! -f "index.html" ]; then
    echo "❌ index.html 不存在"
    exit 1
fi

echo "✅ index.html 存在"


# 测试2：检查 HTML 基本结构
if ! grep -qi "<html" index.html; then
    echo "❌ HTML 结构异常"
    exit 1
fi

echo "✅ HTML 基本结构正常"


# 测试3：检查关键内容
if ! grep -q "欢迎来到我的企业网站" index.html; then
    echo "❌ 网站关键内容缺失"
    exit 1
fi

echo "✅ 网站关键内容正常"


echo "===================================="
echo "🎉 ALL TESTS PASSED"
echo "===================================="