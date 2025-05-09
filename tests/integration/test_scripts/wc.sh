#!/bin/sh

# Bog standard behaviour of wc

set -e

# Create a test file with 4 lines
cat > test.txt << EOF
Line the first
Line 2

Line 4 because 3 was missing.
EOF

# Count each thing in order
wc -l test.txt
wc -c test.txt
wc -w test.txt

# Now each combo
wc -lc test.txt
wc -wl test.txt
wc -wc test.txt

# And finally, the default
wc test.txt
