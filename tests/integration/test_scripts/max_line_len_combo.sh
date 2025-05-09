#!/bin/sh

echo 1         >  one
echo 1st       >> one
echo first     >> one

echo two       >  two
echo 2nd       >> two
echo secondist >> two

echo third     >  three

wc -cwmL one two three
