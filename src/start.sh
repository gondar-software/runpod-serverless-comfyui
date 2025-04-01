#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"
ln -s /runpod-volume /workspace

mkdir -p "$COMFY_OUTPUT_PATH"

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "runpod-worker-comfy: Starting ComfyUI"
    /workspace/ComfyUI/venv/bin/python /workspace/ComfyUI/main.py --disable-auto-launch --disable-metadata --listen --output-directory "$COMFY_OUTPUT_PATH" &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py --rp_serve_api --rp_api_host=0.0.0.0
    python3 /init.py
else
    echo "runpod-worker-comfy: Starting ComfyUI"
    /workspace/ComfyUI/venv/bin/python /workspace/ComfyUI/main.py --disable-auto-launch --disable-metadata --output-directory "$COMFY_OUTPUT_PATH" &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py
    python3 /init.py
fi