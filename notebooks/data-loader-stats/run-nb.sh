#!/usr/bin/env bash

set -e

cd "$(dirname "${BASH_SOURCE[@]}")"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <output name>" >&2
    exit 1
fi

out_dir="$1"; shift
mkdir -p "$out_dir"

nb="nb.ipynb"
out_nb="$out_dir/$nb"
papermill -p out_dir $out_dir -p show png "$nb" "$out_nb"
juq papermill-clean -i "$out_nb"
