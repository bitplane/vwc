#!/bin/sh

printf "cr\r\ronly\r"                > cr.txt
printf "Messed\r\nup\n\n\r\rugh\n\r" > broken.txt

wc cr.txt broken.txt

