FROM python:3.10-slim-bookworm

# Install system dependencies (build-essential needed for netifaces compilation,
# libgraphviz-dev needed for pygraphviz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgraphviz-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy and install Hailo wheels
COPY hailo_dataflow_compiler-3.33.1-py3-none-linux_x86_64.whl /tmp/
COPY hailort-4.23.0-cp310-cp310-linux_x86_64.whl /tmp/

RUN pip install --no-cache-dir /tmp/hailort-4.23.0-cp310-cp310-linux_x86_64.whl \
    && pip install --no-cache-dir /tmp/hailo_dataflow_compiler-3.33.1-py3-none-linux_x86_64.whl \
    && rm /tmp/*.whl

# Default command
CMD ["bash"]
