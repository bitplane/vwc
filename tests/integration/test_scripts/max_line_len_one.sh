#!/bin/sh

echo 1         >  one
echo 1st       >> one
echo first     >> one

wc -L one
