#!/bin/bash

array="[[NSArray alloc] initWithObjects:"

i=0
for file in *.png; do
	if [ $i -gt 0 ]; then
		array="$array, "
	fi
	array="$array [UIImage imageNamed:@\"$file\"]"
	i=$((i+1))
done
array="$array, nil];"
echo $array