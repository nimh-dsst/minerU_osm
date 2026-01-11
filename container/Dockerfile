FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

LABEL maintainer="Adam Thomas"
LABEL description="MinerU PDF-to-JSON conversion container for NIH Biowulf"
LABEL version="2.7.1"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Update and install base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    wget \
    bc \
    && rm -rf /var/lib/apt/lists/*

# Set python3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Install MinerU 2.7.1 with core dependencies
# This version supports vlm-auto-engine and hybrid-auto-engine backends
RUN pip3 install --no-cache-dir "mineru[core]==2.7.1"

# Install additional dependencies for processing scripts
RUN pip3 install --no-cache-dir \
    pandas \
    pyarrow \
    duckdb

# Environment
ENV LC_ALL=C
ENV LANG=C.UTF-8
ENV PATH=/usr/local/bin:$PATH

# Default command
CMD ["mineru", "--help"]
