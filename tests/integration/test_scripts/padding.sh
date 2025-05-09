#!/bin/sh

set -e

printf "012345678" > nine
printf "01234"     > five

wc nine
wc five five five five