#!/bin/bash
# ============================================================
# ONNX to HEF Conversion Script
# Builds a Docker container with Hailo DFC and runs conversion
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="hailo-dfc-converter"
CONTAINER_NAME="hailo-convert"

# Configuration — adjust these as needed
HW_ARCH="${HW_ARCH:-hailo8}"        # hailo8, hailo8l, or hailo10h
INPUT_H="${INPUT_H:-640}"            # Input height
INPUT_W="${INPUT_W:-640}"            # Input width
ONNX_FILE="${ONNX_FILE:-best.onnx}"  # ONNX model filename
CALIB_DATA="${CALIB_DATA:-/workspace/dataset/images/train}" # Optional calibration dataset path

echo ""
echo "============================================"
echo "  Hailo ONNX → HEF Converter"
echo "============================================"
echo "  HW Arch:    ${HW_ARCH}"
echo "  Input Size: ${INPUT_H}x${INPUT_W}"
echo "  ONNX File:  ${ONNX_FILE}"
echo "============================================"
echo ""

# Step 1: Build Docker image
echo "📦 Building Docker image '${IMAGE_NAME}'..."
docker build -t "${IMAGE_NAME}" "${SCRIPT_DIR}"
echo "✅ Docker image built successfully"
echo ""

# Step 2: Run conversion inside container
echo "🚀 Starting conversion..."
docker run --rm \
    --name "${CONTAINER_NAME}" \
    -e USER=root \
    -v "${SCRIPT_DIR}:/workspace" \
    "${IMAGE_NAME}" \
    python3 /workspace/convert_onnx_to_hef.py \
        --onnx "/workspace/${ONNX_FILE}" \
        --hw-arch "${HW_ARCH}" \
        --input-height "${INPUT_H}" \
        --input-width "${INPUT_W}" \
        --calib-data "${CALIB_DATA}"

# Step 3: Check output
MODEL_NAME="${ONNX_FILE%.onnx}"
HEF_FILE="${SCRIPT_DIR}/${MODEL_NAME}.hef"

if [ -f "${HEF_FILE}" ]; then
    echo ""
    echo "============================================"
    echo "🎉 SUCCESS!"
    echo "  HEF file: ${HEF_FILE}"
    echo "  Size:     $(du -h "${HEF_FILE}" | cut -f1)"
    echo ""
    echo "  Transfer to your RPi5:"
    echo "  scp ${HEF_FILE} pi@<rpi-ip>:~/"
    echo "============================================"
else
    echo ""
    echo "❌ ERROR: HEF file not found at ${HEF_FILE}"
    echo "   Check the conversion logs above for errors."
    exit 1
fi
