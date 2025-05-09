#!/bin/sh
# run_test.sh - Run a test comparing original wc and vwc

# Arguments:
# $1 - Test script path
# $2 - Output directory
# $3 - Command to run as wc (either "wc" or "vwc")

# don't have realpath in POSIX
TEST_SCRIPT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_DIR="$2"
WC_COMMAND="$3"

# Create temp directory for PATH manipulation
TEMP_DIR=$(mktemp -d)

# Create symlink from wc to the specified command
ln -sf "$(which "$WC_COMMAND")" "$TEMP_DIR/wc"

# Run the test with our modified PATH, capturing all outputs
export PATH="$TEMP_DIR:$PATH"

cd "$OUTPUT_DIR" || exit 1

"$TEST_SCRIPT" > "2.stdout" 2> "1.stderr"
echo $? > "exitcode"
"$TEST_SCRIPT" > "3.combined" 2>&1

# Clean up
rm -rf "$TEMP_DIR"
