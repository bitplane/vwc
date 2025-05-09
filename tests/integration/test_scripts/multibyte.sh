#!/bin/sh
# Test multi-byte characters

set -e

  cat > utf8.txt << EOF
English text
日本語のテキスト
Emoji test: 😀 🌍 🚀
Wide emoji: 👨‍👩‍👧‍👦
EOF

echo "c:"
wc -c utf8.txt
echo "m:"
wc -m utf8.txt
echo "L:"
wc -L utf8.txt
