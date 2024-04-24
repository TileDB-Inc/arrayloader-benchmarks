#!/usr/bin/env bash
#
# Run this script on a fresh EC2 instance (AMI ) to initialize and run a simple benchmark; see
# README.md for more info.
#
# ```bash
# ./init-instance.sh
# ```

set -ex

# System deps
sudo yum update -y && sudo yum install -y git htop jq patch tree wget

# Install dotfiles, `install_{devtools,cmake,conda}` helpers used below
# See https://github.com/runsascoded/.rc.
. <(curl -L https://j.mp/_rc) runsascoded/.rc

# Install more recent GCC (TileDB-SOMA build seems to require ≥11, definitely >8, instance comes with 7.3.1)
# See https://github.com/ryan-williams/linux-helpers/blob/1421be8d99b3c494b64bf1f4cabdaa25c38e16f3/.yum-rc#L18-L36.
install_devtools 11

# Install more recent CMake (TileDB-SOMA build requires ≥3.21, instance comes with 2.8.x)
# See https://github.com/ryan-williams/linux-helpers/blob/1421be8d99b3c494b64bf1f4cabdaa25c38e16f3/.pkg-rc#L76-L86.
install_cmake 3.29.2

# Install Conda, configure libmamba solver
# See https://github.com/ryan-williams/py-helpers/blob/4996a89ca68e98e364a3e6b23d204f2fb1aa1588/.conda-rc#L1-L32.
install_conda

# Clone this repo
ssh-keyscan -t ecdsa github.com >> .ssh/known_hosts
git clone --recurse-submodules git@github.com:ryan-williams/arrayloader-benchmarks.git
cd arrayloader-benchmarks

# Install/Configure Conda+env
env=arrayloader-benchmarks
conda env update -n $env -f environment.yml --solver libmamba
conda activate $env
echo "conda activate $env" >> ~/.bash_profile

# Install local pip deps, including editable tiledb-soma and cellxgene_census
pip install -r requirements.txt

# Export Census subset to data/census-benchmark_2:7
nb=download-census-slice.ipynb
mkdir out
papermill $nb out/$nb

# Run benchmark notebook on 133k cell Census subset located at data/census-benchmark_2:7
# More info on parameters to this script below.
execute-nb subset-gp3
