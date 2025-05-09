#!/bin/sh

printf "\r\nWindowsy\r\n"           > win.txt
printf "Windowsy\r\nWithout Final"  > win_eof.txt

wc win.txt win_eof.txt

printf "cr\r\ronly\r"                > cr.txt
printf "Messed\r\nup\n\n\r\rugh\n\r" > broken.txt
