#!/bin/sh

set -e

# Send input via pipe and count words
echo "hello world this is a test" | wc -w