#!/bin/sh

set -e

# Create a test file with 3 lines
cat > test.txt << EOF
Line 1
Line 2
Line 3
EOF

# Count the lines
wc -l test.txt
