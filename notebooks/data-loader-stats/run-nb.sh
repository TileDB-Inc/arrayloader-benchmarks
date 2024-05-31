#!/usr/bin/env bash

set -e

cd "$(dirname "${BASH_SOURCE[@]}")"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <output name>" >&2
    exit 1
fi

out_dir="$1"; shift
mkdir -p "$out_dir"

../papermill-clean -p out_dir $out_dir nb.ipynb $out_dir/nb.ipynb
