#!/bin/sh

# Exercise GNU-only options. BusyBox does not expose --files0-from.
if ! wc --help 2>&1 | grep -q -- '--files0-from'; then
    printf 'GNU options unavailable\n'
    exit 0
fi

printf 'one\n' > first
printf 'two words\n' > second
printf 'first\0second\0' > names
printf 'first\0second' > names_no_final_nul
printf 'first\0\0second\0' > names_with_empty
: > empty_names

wc --files0-from=names
wc --files0-from=names_no_final_nul
wc --files0-from=names_with_empty
printf 'status:%s\n' "$?"
wc --files0-from=missing_names
printf 'status:%s\n' "$?"
wc --files0-from=missing_names --total=always
printf 'status:%s\n' "$?"
wc --files0-from=empty_names --total=always
wc --files0-from=names first
printf 'status:%s\n' "$?"
printf '%s\0' - | wc --files0-from=-
printf 'status:%s\n' "$?"
wc --total=always first
wc --total=only first second
wc --total=never first second
