#!/bin/bash
#set -x

for file in `find . -name *.java`; do
	if [ `grep -c ${1} ${file}` -gt 0 ]; then
		echo "${file}"
	fi
done