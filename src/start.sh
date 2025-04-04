#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"
ln -s /runpod-volume /workspace

mkdir -p "$COMFY_OUTPUT_PATH"

git config --global credential.helper store
if command -v /workspace/ComfyUI/venv/bin/huggingface-cli >/dev/null 2>&1; then
    /workspace/ComfyUI/venv/bin/huggingface-cli login --token "$HUGGINGFACE_TOKEN" --add-to-git-credential
else
    echo "huggingface-cli not found. Skipping."
fi

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "runpod-worker-comfy: Starting ComfyUI"
    /workspace/ComfyUI/venv/bin/python /workspace/ComfyUI/main.py --disable-auto-launch --disable-metadata --listen --output-directory "$COMFY_OUTPUT_PATH" &
    python3 /init.py &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    echo "runpod-worker-comfy: Starting ComfyUI"
    /workspace/ComfyUI/venv/bin/python /workspace/ComfyUI/main.py --disable-auto-launch --disable-metadata --output-directory "$COMFY_OUTPUT_PATH" &
    python3 /init.py &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py
fi