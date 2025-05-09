#!/bin/sh

printf "cr\r\ronly\r"                > cr.txt
printf "lf\n\nonly\n"                > lf.txt
printf "Windowsy\r\nWithout Final"   > win.txt
printf "Messed\r\nup\n\n\r\rugh\n\r" > broken.txt

wc cr.txt lf.txt win.txt broken.txt
