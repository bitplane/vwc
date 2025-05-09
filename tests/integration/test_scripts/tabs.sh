#!/bin/sh
set -e

# Create test files with various special characters and tabs
cat > tabs.txt << EOF
Simple	tabbed	text
With		multiple	tabs
EOF

# Test tab handling with max line length
wc -c tabs.txt
wc -m tabs.txt
wc -L tabs.txt
