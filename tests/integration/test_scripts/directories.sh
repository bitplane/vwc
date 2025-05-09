#!/bin/sh

mkdir dir1
echo "file contents" > file1
mkdir dir2

wc dir1 file1 dir2
