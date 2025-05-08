# tests/integration/dockerfiles/Dockerfile.gnu
FROM ubuntu:latest

# Install dependencies
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy everything from the build context
COPY . .

# Verify that pyproject.toml exists (for debugging)
RUN ls -la && \
    cat pyproject.toml

# Install dependencies only (using editable mode with a minimal package structure)
RUN mkdir -p src/vwc && \
    touch src/vwc/__init__.py && \
    pip3 install --break-system-packages -e .

# Default command
CMD ["/bin/bash"]
