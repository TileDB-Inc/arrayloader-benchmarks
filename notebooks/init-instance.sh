#!/usr/bin/env bash
#
# Run this script on a fresh EC2 instance (AMI ami-0de53a7d1c2790c36) to initialize and run a simple benchmark; see
# README.md for more info.
#
# ```bash
# . <(curl https://raw.githubusercontent.com/ryan-williams/arrayloader-benchmarks/main/notebooks/init-instance.sh)
# ```

set -ex

branch=2025_profiling
cmake=1
conda=1
docker=
devtools=1
host=
parquet2json=
dotfiles=
while [ $# -gt 0 ]; do
    arg="$1"; shift
    case "$arg" in
        -A|--no-conda) conda= ;;
        -b|--branch)
            if [ $# -eq 0 ]; then
                echo "Expected argument after --branch" >&2
                exit 1
            fi
            branch="$1"; shift ;;
        -C|--no-cmake) cmake= ;;
        -d|--docker) docker=1 ;;
        -D|--no-devtools) devtools= ;;
        -h|--host)
            if [ $# -eq 0 ]; then
                echo "Expected argument after --host" >&2
                exit 1
            fi
            host="$1"; shift ;;
        --p2j|--parquet2json) parquet2json=1 ;;
        --rc|--dotfiles) dotfiles=1 ;;
        *)
            echo "Unrecognized argument: $arg" >&2
            exit 1 ;;
    esac
done


# System deps
sudo yum update -y && sudo yum install -y git jq patch

if [ -n "$host" ]; then
    echo "export host=$host" >> ~/.bash_profile
fi

# Install more recent GCC (TileDB-SOMA build seems to require ≥11, definitely >8, instance comes with 7.3.1)
# install_devtools() {
#     # Adapted from https://stackoverflow.com/a/66376026/23555888
#     local v="${1:-11}"
#     sudo yum-config-manager --add-repo http://mirror.centos.org/centos/7/sclo/x86_64/rh/
#     sudo yum install -y wget

#     fortran=libgfortran5-8.3.1-2.1.1.el7.x86_64.rpm
#     wget http://mirror.centos.org/centos/7/os/x86_64/Packages/$fortran
#     sudo yum install $fortran -y
#     rm $fortran

#     sudo yum install -y devtoolset-$v --nogpgcheck
#     local enable=/opt/rh/devtoolset-$v/enable
#     . "$enable"
#     echo >> ~/.bash_profile
#     echo "# Use GCC $v" >> ~/.bash_profile
#     echo ". \"$enable\"" >> ~/.bash_profile
#     which -a gcc
# }
install_devtools() {
  sudo tee /etc/yum.repos.d/centos-sclo.repo >/dev/null <<'EOF'
[centos-sclo-rh]
name=CentOS‑7 - SCLo rh (vault)
baseurl=https://vault.centos.org/7.9.2009/sclo/x86_64/rh/
enabled=1
gpgcheck=0
EOF
  sudo yum clean all
  echo "Test 1"
  sudo yum makecache
  echo "Test 2"
  sudo yum install -y devtoolset-"${1:-11}"
  echo "Test 3"
  source /opt/rh/devtoolset-"${1:-11}"/enable
  echo ". /opt/rh/devtoolset-${1:-11}/enable" >> ~/.bash_profile
}

if [ -n "$devtools" ]; then
    install_devtools 11
fi

# Install more recent CMake (TileDB-SOMA build requires ≥3.21, instance comes with 2.8.x)
install_cmake() {
    cmake_version="${1:-3.29.2}"
    cmake_stem=cmake-$cmake_version-linux-x86_64
    wget https://github.com/Kitware/CMake/releases/download/v$cmake_version/$cmake_stem.sh
    local dir="$HOME/$cmake_stem"
    mkdir -p "$dir"
    bash $cmake_stem.sh --skip-license --prefix="$dir" && rm $cmake_stem.sh
    export PATH="$HOME/$cmake_stem/bin:$PATH"
    echo >> ~/.bash_profile
    echo "# Use CMake $cmake_version; see https://github.com/ryan-williams/linux-helpers/blob/main/.pkg-rc" >> ~/.bash_profile
    echo "export PATH=\"\$HOME/$cmake_stem/bin:\$PATH\"" >> ~/.bash_profile
    cmake --version
}
if [ -n "$cmake" ]; then
    install_cmake 3.29.2
fi

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
if [ -n "$conda" ]; then
    install_conda
fi

# Clone this repo
# ssh-keyscan -t ecdsa github.com >> .ssh/known_hosts
git clone -b "$branch" --recurse-submodules https://github.com/ryan-williams/arrayloader-benchmarks.git
cd arrayloader-benchmarks
echo "cd ~/arrayloader-benchmarks" >> ~/.bash_profile

# Install/Configure Conda+env
env=arrayloader-benchmarks
conda env update -n $env -f environment.yml --solver libmamba
conda activate $env
echo "conda activate $env" >> ~/.bash_profile
conda env list

# Install this library (including editable tiledb-soma and cellxgene_census)
pip install -e . -e cellxgene-census/api/python/cellxgene_census -e tiledb-soma/apis/python

if [ -n "$docker" ]; then
    sudo yum install -y docker
    sudo service docker start
    sudo systemctl enable docker
    sudo usermod -a -G docker $USER
    echo "Added user $USER to docker group, but you'll need to log out and back in for it to take effect" >&2
fi

if [ -n "$dotfiles" ]; then
    . <(curl -L https://j.mp/_rc) runsascoded/.rc
    sudo yum install -y emacs htop
fi

if [ -n "$parquet2json" ]; then
    # Install Rust
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    . $HOME/.cargo/env
    echo ". $HOME/.cargo/env" >> ~/.bash_profile
    rustup update
    cargo install parquet2json
fi
set +ex
