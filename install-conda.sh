#!/usr/bin/env bash

if [ $# -gt 0 ]; then
    d="$1"
    path_args=(-p "$@")
else
    d="$HOME/miniconda3"
    path_args=()
fi
os="$(uname -s)"
if [ "$os" == "Darwin" ]; then
    os="MacOSX"
fi
arch="$(uname -m)"
base="https://repo.anaconda.com/miniconda"
name="$(curl "$base/" | grep "$os" | grep latest | grep -m1 "$arch" | grep -o 'Miniconda3.*sh">' | grep -o '.*.sh')"
if [ -z "$name" ]; then
    echo "Failed to find Miniconda3 installer for $os $arch at $base" >&2
    return 1
fi
sh_url="$base/$name"
echo "Downloading $sh_url" >&2
wget -Ominiconda.sh "$sh_url"
bash miniconda.sh -b "${path_args[@]}"
rm miniconda.sh
. $d/etc/profile.d/conda.sh
echo ". $d/etc/profile.d/conda.sh" >> ~/.bashrc
conda install -y -n base conda-libmamba-solver
conda config --set solver libmamba
conda activate base
