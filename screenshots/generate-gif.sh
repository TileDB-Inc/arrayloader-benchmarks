#!/usr/bin/env bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <cdf|ratios>"
    exit 1
fi
name="$1"

convert -delay 200 ${name}{-hover,,-hover}.png ${name}.gif
