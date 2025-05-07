#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

git config --global credential.helper store
if command -v /root/ComfyUI/venv/bin/huggingface-cli >/dev/null 2>&1; then
    /root/ComfyUI/venv/bin/huggingface-cli login --token "$HUGGINGFACE_TOKEN" --add-to-git-credential
else
    echo "huggingface-cli not found. Skipping."
fi

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "runpod-worker-comfy: Starting ComfyUI"
    /root/ComfyUI/venv/bin/python /root/ComfyUI/main.py --disable-auto-launch --disable-metadata --listen &
    python /init.py &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python -u /rp_handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    echo "runpod-worker-comfy: Starting ComfyUI"
    /root/ComfyUI/venv/bin/python /root/ComfyUI/main.py --disable-auto-launch --disable-metadata &
    python /init.py &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python -u /rp_handler.py
fi