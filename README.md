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

#### 1. Launch instance
Example using a g4dn.8xlarge and AMI [`ami-0de53a7d1c2790c36`] ("Amazon Linux 2 AMI with NVIDIA TESLA GPU Driver"), with [`launch_instance.py`]:
```bash
instance="$(launch_instance.py -a ami-0de53a7d1c2790c36 -i g4dn.8xlarge)"
ssh $instance
```

#### 2. Initialize instance
Eval [`init-instance.sh`] (assumes Amazon Linux):
```bash
. <(curl https://raw.githubusercontent.com/ryan-williams/arrayloader-benchmarks/main/init-instance.sh)
```
The CMake install will prompt you for a `y` a couple times.

This will:
- Install system deps
- Configure a Conda env (named `arrayloader-benchmarks`)
- Download a 133k-cell subset of the Census to `data/census-benchmark_2:7` (see [download-census-slice.ipynb]).
- Execute [benchmark.ipynb] on that dataset, writing an output notebook to [benchmarks/subset-gp3.ipynb] (see [execute-nb]).

If you then open [benchmarks/subset-gp3.ipynb], you'll see some timings related to loading those 133k cells with Census/SOMA.

#### 3. Run benchmarks
[execute-nb](execute-nb) supports running [benchmark.ipynb] on various Census slices and localities: 
```bash
./execute-nb us-east-1  # from a g4dn.8xlarge in us-east-1
./execute-nb us-west-2  # from a g4dn.8xlarge in us-west-2
./execute-nb local-nvme -p census_uri '/mnt/nvme/s3/cellxgene-census-public-us-west-2/cell-census/2023-12-15/soma'
./execute-nb subset-nvme -p experiment_uri '/mnt/nvme/census-benchmark_2:7' -p n_vars 0  # 20k vars already sliced
./execute-nb subset-gp3 -p experiment_uri 'data/census-benchmark_2:7' -p n_vars 0  # 20k vars already sliced
```

## GC / Batch fetching account for most total latency
See some earlier analysis at [gc-batch-fetching.md].


[laminlabs/arrayloader-benchmarks]: https://github.com/laminlabs/arrayloader-benchmarks
[A large-scale benchmark]: https://lamin.ai/blog/arrayloader-benchmarks#a-large-scale-benchmark

[a subset of Census]: download-census-slice.ipynb

[`ami-0de53a7d1c2790c36`]: https://aws.amazon.com/marketplace/pp/prodview-64e4rx3h733ru
[`init-instance.sh`]: init-instance.sh

[benchmark.ipynb]: benchmark.ipynb
[benchmarks/subset-gp3.ipynb]: benchmarks/subset-gp3.ipynb
[`launch_instance.py`]: https://github.com/ryan-williams/aws-helpers/blob/main/launch_instance.py
[download-census-slice.ipynb]: download-census-slice.ipynb
[execute-nb]: execute-nb
[gc-batch-fetching.md]: gc-batch-fetching.md
