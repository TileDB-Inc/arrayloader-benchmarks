#!/usr/bin/env bash

set -e

name="$1"; shift
out="benchmarks/$name.ipynb"

cmd=(
  papermill
  benchmark.ipynb
  -p name "$name"
  "$@"
  "$out"
)
echo "Running: ${cmd[*]}" >&2
"${cmd[@]}"

tmp="$(mktemp)"
jq --indent 1 '.cells |= map(del(.id) | .metadata |= del(.papermill,.execution,.widgets)) | del(.metadata.papermill)' "$out" > "$tmp"
mv "$tmp" "$out"
