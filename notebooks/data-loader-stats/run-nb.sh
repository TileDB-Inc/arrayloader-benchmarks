#!/usr/bin/env bash

set -e

cd "$(dirname "${BASH_SOURCE[@]}")"

usage() {
    echo "Usage: $0 [azl|m3]" >&2
    exit 1
}

if [ $# -ne 1 ]; then
    usage
fi

out_dir="$1"; shift
mkdir -p "$out_dir"

if [ "$out_dir" == m3 ]; then
    hostname=m3
    proportional_symbol_size=2em
    host="M3 Mac"
elif [ "$out_dir" == azl ]; then
    hostname=us-west-2
    proportional_symbol_size=1em
    host="EC2 (g4dn.8xlarge)"
else
    usage
fi

nb="nb.ipynb"
out_nb="$out_dir/$nb"
export UTZ_PLOT_SHOW=png
papermill \
    -p out_dir $out_dir \
    -p show png \
    -p host "$host" \
    -p hostname "$hostname" \
    -p W 1200 -p H 800 \
    -p proportional_symbol_size $proportional_symbol_size \
    "$nb" "$out_nb"
juq papermill-clean -i "$out_nb"
