# Stage 1: Base image with common dependencies
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04 as base

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1 
# Speed up some cmake builds
ENV CMAKE_BUILD_PARALLEL_LEVEL=8

# Install Python, git and other necessary tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    libgl1 \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Clone repositories
RUN git clone https://github.com/gondar-software/Voila-ComfyUI /root/ComfyUI && \
    git clone https://github.com/gondar-software/Voila-ComfyUI-load-image-from-url /root/ComfyUI/custom_nodes/ComfyUI-load-image-from-url && \
    git clone https://github.com/gondar-software/Voila-ComfyUI-Manager /root/ComfyUI/custom_nodes/ComfyUI-Manager && \
    git clone https://github.com/gondar-software/Voila-ComfyUI-EasyControl /root/ComfyUI/custom_nodes/ComfyUI-EasyControl

# Install huggingface-downloader (assuming it's a custom script/module)
COPY src/huggingface-downloader.py /root/huggingface-downloader.py
RUN chmod +x /root/huggingface-downloader.py

# Download models (use build-time secrets for HUGGINGFACE_TOKEN)
ARG HUGGINGFACE_TOKEN
RUN \
    pip install huggingface_hub && \
    python /root/huggingface-downloader.py -m "black-forest-labs/FLUX.1-dev" -t "$HUGGINGFACE_TOKEN" -s "/root/ComfyUI/models/" && \
    python /root/huggingface-downloader.py -m "monate615/easycontrols" -t "$HUGGINGFACE_TOKEN" -s "/root/ComfyUI/models/loras/" && \
    mv /root/ComfyUI/models/loras/monate615/easycontrols/* /root/ComfyUI/models/loras/ && \
    rm -r /root/ComfyUI/models/loras/monate615 && \
    rm -r /root/ComfyUI/requirements.txt

# Create virtual environment and install dependencies
COPY src/requirements.txt /root/ComfyUI/requirements.txt
RUN python -m venv /root/ComfyUI/venv && \
    /root/ComfyUI/venv/bin/pip install --no-cache-dir -r /root/ComfyUI/requirements.txt

# Install runpod
RUN pip install runpod requests pillow huggingface_hub

# Go back to the root
WORKDIR /

# Add scripts
ADD src/start.sh src/restore_snapshot.sh src/rp_handler.py src/init.py test_input.json ./
RUN chmod +x /start.sh /restore_snapshot.sh

# Add workflows
ADD workflows/ghibli.json workflows/snoopy.json workflows/3d_cartoon.json workflows/labubu.json workflows/classic_toys.json ./
RUN chmod +x /ghibli.json /snoopy.json /3d_cartoon.json /labubu.json /classic_toys.json

# Optionally copy the snapshot file
ADD *snapshot*.json /

# Restore the snapshot to install custom nodes
RUN /restore_snapshot.sh

# Start container
CMD ["/start.sh"]