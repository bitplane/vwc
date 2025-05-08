#!/bin/bash
# tests/integration/build.sh - Prepare build directory

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"

# Create build directory
if [ -d "${BUILD_DIR:?}" ]; then
    rm -rf "${BUILD_DIR:?}"/*
else
    mkdir -p "$BUILD_DIR"
fi

# Copy required files
cp "$PROJECT_ROOT/pyproject.toml" "$BUILD_DIR/"
cp "$PROJECT_ROOT/README.md" "$BUILD_DIR/"

echo "Build directory prepared with required files"
