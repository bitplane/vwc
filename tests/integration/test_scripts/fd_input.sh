#!/bin/sh

# shellcheck disable=SC3001
wc <(yes hello | head -n10000)
