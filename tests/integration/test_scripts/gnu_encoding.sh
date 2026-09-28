#!/bin/sh

if ! wc --help 2>&1 | grep -q -- '--files0-from'; then
    printf 'GNU locale cases unavailable\n'
    exit 0
fi

printf '\303\251\377\n' > mixed
printf 'wide: \347\225\214\tX\n' > wide_tab
printf 'ab\rc\nab\fcd\n' > controls
printf 'a\240b\n' > c_nbsp

LC_ALL=C.UTF-8 wc -m -w -L mixed wide_tab controls
LC_ALL=C wc -m -w -L mixed wide_tab controls
LC_ALL=C wc -w c_nbsp
