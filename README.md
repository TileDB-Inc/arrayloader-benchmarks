# `arrayloader-benchmarks`

This fork of [laminlabs/arrayloader-benchmarks] digs further into timings from "[A large-scale benchmark]" / [Plot Figure 1.ipynb](Plot%20Figure%201.ipynb).

## Census timing vs. data locality

See [benchmark.ipynb](benchmark.ipynb), and example runs:
- [us-east-1.ipynb](benchmarkes/us-east-1.ipynb): read Census (us-west-2) from an instance in us-east-1
- [us-west-2.ipynb](benchmarkes/us-west-2.ipynb): read Census (us-west-2) from an instance in us-west-2
- [local-nvme.ipynb](benchmarkes/local-nvme.ipynb): read a local copy of Census from an NVMe drive
- [subset-nvme.ipynb](benchmarkes/subset-nvme.ipynb): read a subset of Census from an NVMe drive
- [subset-gp3.ipynb](benchmarkes/subset-gp3.ipynb): read a subset of Census from a gp3 EBS volume

All 5 ran against the same 5 Census datasets (133790 cells), but the "subset" runs read an exported SOMA with just that data (≈714MiB vs. 593GiB); see [download-census-slice.ipynb](download-census-slice.ipynb).

Rough samples/sec numbers:
```bash
cd results; for f in *.json; do
    echo -n "${f%.json}: "
    jq -j '.census.epochs[0].samples_per_sec | floor' $f
    echo ' samples/sec'
done | column -t | sort -nk2
# us-east-1:    884   samples/sec
# us-west-2:    1423  samples/sec
# local-nvme:   1830  samples/sec
# subset-nvme:  2913  samples/sec
# subset-gp3:   3036  samples/sec
```

Plot images are in [img/](img/), e.g. [img/census-us-west-2.png](img/census-us-west-2.png):

![](img/census-us-west-2.png)

### Repro

<details><summary>Set up instance</summary>

Launch g4dn.8xlarge, [`ami-0de53a7d1c2790c36`]: (Amazon Linux 2 AMI with NVIDIA TESLA GPU Driver)

```bash
# Clone repo
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
conda env update -n $env -f environment.yml
conda activate $env
echo "conda activate $env" >> ~/.bash_profile

# Install local pip deps, including editable tiledb-soma and cellxgene_census
pip install -r requirements.txt

# Build a local TileDB-SOMA; this needs to happen after the `pip install` above, for some reason
cd tiledb-soma
make clean && make install
cd ..

# Export Census subset to data/census-benchmark_2:7
nb=download-census-slice.ipynb
mkdir out
papermill $nb out/$nb

# Run benchmark notebook on 133k cell Census subset located at data/census-benchmark_2:7
# More info on parameters to this script below.
execute-nb subset-gp3
```

Dotfiles repo: [runsascoded/.rc], [`install_devtools`], [`install_cmake`], [`install_conda`]
</details>

#### Run benchmarks
```bash
./execute-nb us-east-1  # from a g4dn.8xlarge in us-east-1
./execute-nb us-west-2  # from a g4dn.8xlarge in us-west-2
./execute-nb local-nvme -p census_uri '/mnt/nvme/s3/cellxgene-census-public-us-west-2/cell-census/2023-12-15/soma'
./execute-nb subset-nvme -p experiment_uri '/mnt/nvme/census-benchmark_2:7' -p n_vars 0  # 20k vars already sliced
./execute-nb subset-gp3 -p experiment_uri 'data/census-benchmark_2:7' -p n_vars 0  # 20k vars already sliced
```

See [execute-nb](execute-nb).

## GC / Batch fetching account for most total latency

See batch timings below: 
- Every ≈10th Census batch took ≈30x the average, accounting for ≈80% of total latency.
- Merlin had 3x slower batches every 10, with an even more rigid pattern.
- MappedCollection batch times tended to repeat every 7 batches, with slower batches often 40-50x slower than average.

### Slowest ≈10% of batches account for most {MappedCollection,Census} latency

[![](screenshots/cdf.gif)](screenshots/)

Slowest 10% of batches' share of total latency:
- Merlin: 18-25%
- MappedCollection: 50-62%
- Census: 76-81%

<details><summary>See also: [slower batch times] / [faster batch times]</summary>

[![](screenshots/ratios.gif)](screenshots/)
</details>

### Every 7th or 10th batch was 30x-100x slower

#### Merlin
Batch times (colored by [batch index] mod 10):
[![](img/merlin_batches_mod10.png)](img/merlin_batches_mod10.png)

- In most epochs, every 10th run was ≈3x slower than average
- First epoch was more stable around the overall average, but `1mod10`s were often much *faster*.

<details><summary>Detail: every 10th batch slow</summary>

[![](img/merlin_batches_mod10_1200:1800.png)](img/merlin_batches_mod10_1200:1800.png)

The first epoch exhibited different "every 10th batch" periodicity.
</details>

#### Census
Batch times (colored by [batch index] mod 10):
[![](img/census_batches_mod10.png)](img/census_batches_mod10.png)

Worst 10% of batches were ≈30-40x slower than average

Detail below shows "30x slower" batches repeated roughly every 10, but slipped by 1 every 40-50:

<details><summary>Example slow-batch-gap pattern: 10, 10, 10, 10, 9</summary>

[![](img/census_batches_mod10_1200:1800.png)](img/census_batches_mod10_1200:1800.png)
</details>

#### MappedCollection
Batch times (colored by [batch index] mod **7**):
[![](img/mappedcollection_batches_mod7.png)](img/mappedcollection_batches_mod7.png)

MappedCollection had slow batches every 7 (as opposed to every 10 for the other two methods).

<details><summary>Detail: batch times repeating every 7</summary>

[![](img/mappedcollection_batches_mod7_1200:1800.png)](img/mappedcollection_batches_mod7_1200:1800.png)
</details>

[laminlabs/arrayloader-benchmarks]: https://github.com/laminlabs/arrayloader-benchmarks
[A large-scale benchmark]: https://lamin.ai/blog/arrayloader-benchmarks#a-large-scale-benchmark

[a subset of Census]: download-census-slice.ipynb

[`ami-0de53a7d1c2790c36`]: https://aws.amazon.com/marketplace/pp/prodview-64e4rx3h733ru
[runsascoded/.rc]: https://github.com/runsascoded/.rc
[`install_devtools`]: https://github.com/ryan-williams/linux-helpers/blob/1421be8d99b3c494b64bf1f4cabdaa25c38e16f3/.yum-rc#L18-L36
[`install_cmake`]: https://github.com/ryan-williams/linux-helpers/blob/1421be8d99b3c494b64bf1f4cabdaa25c38e16f3/.pkg-rc#L76-L86
[`install_conda`]: https://github.com/ryan-williams/py-helpers/blob/4996a89ca68e98e364a3e6b23d204f2fb1aa1588/.conda-rc#L1-L32
