#!/bin/sh

printf "lf\n\nonly\n"     > lf.txt
printf "lf\nwithout\nend" > lf_eof.txt

wc cr.txt lf.txt win.txt broken.txt
