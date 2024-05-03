# `arrayloader-benchmarks`

This fork of [laminlabs/arrayloader-benchmarks] digs further into timings from "[A large-scale benchmark]" / [Plot Figure 1.ipynb](Plot%20Figure%201.ipynb).

Install this library, as well as [cellxgene-census] and [tiledb-soma] Git submodules:
```bash
pip install -e . -e cellxgene-census/api/python/cellxgene_census -e tiledb-soma/apis/python
```

Download a small Census slice:
```bash
alb download -s 2 -e 3
```

This downloads [the dataset at index 2, among 138 human datasets in collection `283d65eb-dd53-496d-adb7-7570c7caa443`] to data/census-benchmark_2:3.



[laminlabs/arrayloader-benchmarks]: https://github.com/laminlabs/arrayloader-benchmarks
[A large-scale benchmark]: https://lamin.ai/blog/arrayloader-benchmarks#a-large-scale-benchmark

[cellxgene-census]: cellxgene-census
[tiledb-soma]: tiledb-soma
