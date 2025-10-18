#!/bin/bash
# V2AIX 数据集自动化批处理脚本

set -e  # 遇到错误立即退出

PROJECT_ROOT="/Users/neardws/Documents/data_processing_of_V2AIX_dataset"
JSON_DIR="${PROJECT_ROOT}/json"
OUTPUT_DIR="${PROJECT_ROOT}/output"

echo "========================================="
echo "V2AIX Dataset Batch Processing Script"
echo "========================================="
echo ""

# 检查输入目录是否存在
if [ ! -d "$JSON_DIR" ]; then
    echo "Error: JSON directory not found: $JSON_DIR"
    exit 1
fi

# 1. 处理整个数据集
echo "[1/4] Processing FULL dataset..."
v2aix-pipeline \
    --input "$JSON_DIR" \
    --output-dir "${OUTPUT_DIR}/full" \
    --format parquet \
    --hz 1 \
    --visualize \
    --workers 4

echo "✓ Full dataset processed"
echo ""

# 2. 处理 Mobile 数据
echo "[2/4] Processing MOBILE scenarios..."
v2aix-pipeline \
    --input "${JSON_DIR}/Mobile" \
    --output-dir "${OUTPUT_DIR}/mobile" \
    --format parquet \
    --hz 1 \
    --visualize \
    --workers 4

echo "✓ Mobile scenarios processed"
echo ""

# 3. 处理 Stationary 数据
echo "[3/4] Processing STATIONARY scenarios..."
v2aix-pipeline \
    --input "${JSON_DIR}/Stationary" \
    --output-dir "${OUTPUT_DIR}/stationary" \
    --format parquet \
    --hz 1 \
    --visualize \
    --workers 4

echo "✓ Stationary scenarios processed"
echo ""

# 4. 统计信息
echo "[4/4] Generating summary..."
echo ""
echo "========================================="
echo "Processing Complete!"
echo "========================================="
echo "Output locations:"
echo "  - Full dataset:     ${OUTPUT_DIR}/full"
echo "  - Mobile scenarios: ${OUTPUT_DIR}/mobile"
echo "  - Stationary:       ${OUTPUT_DIR}/stationary"
echo ""
echo "Use 'ls -lh ${OUTPUT_DIR}' to view outputs"
echo "========================================="
