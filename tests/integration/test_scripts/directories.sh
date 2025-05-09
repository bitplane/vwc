#!/bin/sh

mkdir -p dir1
echo "file contents" > file1
mkdir -p dir2

wc dir1 file1 dir2
