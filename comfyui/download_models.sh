#!/bin/bash

set -e

echo "Downloading AI models for ComfyUI..."

MODELS_DIR="/app/ComfyUI/models"

# 1. Face Swap Model (ReActor / inswapper)
mkdir -p "$MODELS_DIR/insightface"
echo "Downloading inswapper_128.onnx..."
if [ ! -f "$MODELS_DIR/insightface/inswapper_128.onnx" ]; then
    curl -L -o "$MODELS_DIR/insightface/inswapper_128.onnx" \
      "https://huggingface.co/Gourieff/ReActor/resolve/main/models/inswapper_128.onnx"
    echo "✓ inswapper_128.onnx downloaded"
else
    echo "✓ inswapper_128.onnx already exists, skipping"
fi

# 2. Image Upscale Model (Real-ESRGAN)
mkdir -p "$MODELS_DIR/upscale_models"
echo "Downloading RealESRGAN_x4plus.pth..."
if [ ! -f "$MODELS_DIR/upscale_models/RealESRGAN_x4plus.pth" ]; then
    curl -L -o "$MODELS_DIR/upscale_models/RealESRGAN_x4plus.pth" \
      "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
    echo "✓ RealESRGAN_x4plus.pth downloaded"
else
    echo "✓ RealESRGAN_x4plus.pth already exists, skipping"
fi

# 3. Remove Background Model (BRIA-RMBG-2.0)
mkdir -p "$MODELS_DIR/rmbg"
echo "Downloading BRIA-RMBG-2.0.pth..."
if [ ! -f "$MODELS_DIR/rmbg/briarmbg_2_0.pth" ]; then
    curl -L -o "$MODELS_DIR/rmbg/briarmbg_2_0.pth" \
      "https://huggingface.co/briaai/RMBG-2.0/resolve/main/model.pth"
    echo "✓ BRIA-RMBG-2.0.pth downloaded"
else
    echo "✓ BRIA-RMBG-2.0.pth already exists, skipping"
fi

echo ""
echo "All models ready!"
echo "Model sizes:"
du -sh "$MODELS_DIR"/*/ 2>/dev/null || echo "Models directory structure created"
