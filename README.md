# `arrayloader-benchmarks`

This fork of [laminlabs/arrayloader-benchmarks] digs further into timings from "[A large-scale benchmark]" / [Plot Figure 1.ipynb](Plot%20Figure%201.ipynb).

## Install
Install this library, as well as [cellxgene-census] and [tiledb-soma] Git submodules:

```bash
pip install -e cellxgene-census/api/python/cellxgene_census
pip install -e tiledb-soma/apis/python
pip install -e .
```

## Prepare a local dataset
Generate a local copy of a small Census slice:
```bash
# - Open the datasets at index 2 and 3 (slice `2:4`) within collection_id 283d65eb-dd53-496d-adb7-7570c7caa443 (default: `-c 283d65eb-dd53-496d-adb7-7570c7caa443`)
# - Slice the first 20k vars (default: `-v 20_000`)
# - Save to data/census-benchmark_2:3 (default: `-d data`)
alb download -s 2 -e 4
```

Or download a pre-sliced dataset:
```bash
dst=data/census-benchmark_2:4
aws s3 sync s3://rw-tdb-west2/arrayloader-benchmarks/$dst $dst
```

## Benchmark

No shuffle:
```bash
alb read-chunks data/census-benchmark_2:4
# read_table elapsed: 1.43s
# read_blockwise_table elapsed: 2.33s
# read_blockwise_scipy_coo elapsed: 10.36s
# read_blockwise_scipy_csr elapsed: 13.92s
```

Intra-chunk shuffle:
```bash
alb read-chunks -s data/census-benchmark_2:4
# read_table elapsed: 1.50s
# read_blockwise_table elapsed: 2.70s
# read_blockwise_scipy_coo elapsed: 12.83s
# read_blockwise_scipy_csr elapsed: 19.29s
```

Global shuffle:
```bash
alb read-chunks -ss data/census-benchmark_2:4
# read_table elapsed: 21.04s
# read_blockwise_table elapsed: 21.47s
# read_blockwise_scipy_coo elapsed: 35.60s
# read_blockwise_scipy_csr elapsed: 37.63s
```

[laminlabs/arrayloader-benchmarks]: https://github.com/laminlabs/arrayloader-benchmarks
[A large-scale benchmark]: https://lamin.ai/blog/arrayloader-benchmarks#a-large-scale-benchmark

[cellxgene-census]: cellxgene-census
[tiledb-soma]: tiledb-soma
