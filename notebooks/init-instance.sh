#!/usr/bin/env bash
#
# Run this script on a fresh EC2 instance (AMI ami-0de53a7d1c2790c36) to initialize and run a simple benchmark; see
# README.md for more info.
#
# ```bash
# . <(curl https://raw.githubusercontent.com/ryan-williams/arrayloader-benchmarks/main/init-instance.sh)
# ```

set -ex

branch="${1:-main}"

# System deps
sudo yum update -y && sudo yum install -y git jq patch

# Install more recent GCC (TileDB-SOMA build seems to require ≥11, definitely >8, instance comes with 7.3.1)
install_devtools() {
    # Adapted from https://stackoverflow.com/a/66376026/23555888
    local v="${1:-11}"
    sudo yum-config-manager --add-repo http://mirror.centos.org/centos/7/sclo/x86_64/rh/
    sudo yum install -y wget

    fortran=libgfortran5-8.3.1-2.1.1.el7.x86_64.rpm
    wget http://mirror.centos.org/centos/7/os/x86_64/Packages/$fortran
    sudo yum install $fortran -y
    rm $fortran

    sudo yum install -y devtoolset-$v --nogpgcheck
    local enable=/opt/rh/devtoolset-$v/enable
    . "$enable"
    echo >> ~/.bash_profile
    echo "# Use GCC $v" >> ~/.bash_profile
    echo ". \"$enable\"" >> ~/.bash_profile
    which -a gcc
}
install_devtools 11

# Install more recent CMake (TileDB-SOMA build requires ≥3.21, instance comes with 2.8.x)
install_cmake() {
    cmake_version="${1:-3.29.2}"
    cmake_stem=cmake-$cmake_version-linux-x86_64
    wget https://github.com/Kitware/CMake/releases/download/v$cmake_version/$cmake_stem.sh
    bash $cmake_stem.sh
    export PATH="$HOME/$cmake_stem/bin:$PATH"
    echo >> ~/.bash_profile
    echo "# Use CMake $cmake_version; see https://github.com/ryan-williams/linux-helpers/blob/main/.pkg-rc" >> ~/.bash_profile
    echo "export PATH=\"\$HOME/$cmake_stem/bin:\$PATH\"" >> ~/.bash_profile
    cmake --version
}
install_cmake 3.29.2

# Install Conda, configure libmamba solver
install_conda() {
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
}
install_conda

# Clone this repo
ssh-keyscan -t ecdsa github.com >> .ssh/known_hosts
git clone -b "$branch" --recurse-submodules git@github.com:ryan-williams/arrayloader-benchmarks.git
cd arrayloader-benchmarks

# Install/Configure Conda+env
env=arrayloader-benchmarks
conda env update -n $env -f environment.yml --solver libmamba
conda activate $env
echo "conda activate $env" >> ~/.bash_profile
conda env list

# Install this library (including editable tiledb-soma and cellxgene_census)
pip install -e .

# Export Census subset to data/census-benchmark_2:7
nb=download-census-slice.ipynb
mkdir out
papermill $nb out/$nb

# Run benchmark notebook on 133k cell Census subset located at data/census-benchmark_2:7
# More info on parameters to this script below.
./execute-nb subset-gp3

set +ex
