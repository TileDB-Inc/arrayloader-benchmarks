# `arrayloader-benchmarks`

This fork of [laminlabs/arrayloader-benchmarks] digs further into timings from "[A large-scale benchmark]" / [Plot Figure 1.ipynb](Plot%20Figure%201.ipynb).

## Install
Install this library, as well as [cellxgene-census] and [tiledb-soma] Git submodules:
```bash
pip install -e . -e cellxgene-census/api/python/cellxgene_census -e tiledb-soma/apis/python
```

## Prepare a local dataset
Generate a local copy of a small Census slice:
```bash
# - Open the datasets at index 2 and 3 (slice `2:4`) within collection_id 283d65eb-dd53-496d-adb7-7570c7caa443 (default: `-c 283d65eb-dd53-496d-adb7-7570c7caa443`)
# - Slice the first 20k vars (default: `-v 20_000`)
# - Save to data/census-benchmark_2:3 (default: `-d data`)
alb download -s 2 -e 4
```
Or download from S3:
```bash
aws s3 sync --exclude '*' --include 'census-benchmark_2:4/*' s3://tiledb-rw/arrayloader-benchmarks/ data/
```

## Benchmark
```bash
alb 
```

[laminlabs/arrayloader-benchmarks]: https://github.com/laminlabs/arrayloader-benchmarks
[A large-scale benchmark]: https://lamin.ai/blog/arrayloader-benchmarks#a-large-scale-benchmark

[cellxgene-census]: cellxgene-census
[tiledb-soma]: tiledb-soma

`case.exp_path`, `case.original`,
`case.new`,
`case.new_obs`,
`case.new_var`,
`case.o1`,
`case.v1`,
