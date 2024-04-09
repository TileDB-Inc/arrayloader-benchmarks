# `arrayloader-benchmarks`

This fork of [laminlabs/arrayloader-benchmarks] adds [fig-1-batch-times.ipynb](fig-1-batch-times.ipynb), which examines batch timings from "[A large-scale benchmark]" / [Plot Figure 1.ipynb](Plot%20Figure%201.ipynb).

In particular:
- Every ≈10th Census batch took ≈30x the average, accounting for ≈80% of total latency.
- Merlin had 3x slower batches every 10, with an even more rigid pattern.
- MappedCollection batch times tended to repeat every 7 batches, with slower batches often 40-50x slower than average.

## Slowest ≈10% of batches account for most {MappedCollection,Census} latency

[![](screenshots/cdf.gif)](screenshots/)

Slowest 10% of batches' share of total latency:
- Merlin: 18-25%
- MappedCollection: 50-62%
- Census: 76-81%

<details><summary>See also: [slower batch times] / [faster batch times]</summary>

[![](screenshots/ratios.gif)](screenshots/)
</details>

## Every 7th or 10th batch was 30x-100x slower

### Merlin
Batch times (colored by [batch index] mod 10):
[![](img/merlin_batches_mod10.png)](img/merlin_batches_mod10.png)

- In most epochs, every 10th run was ≈3x slower than average
- First epoch was more stable around the overall average, but `1mod10`s were often much *faster*.

<details><summary>Detail: every 10th batch slow</summary>

[![](img/merlin_batches_mod10_1200:1800.png)](img/merlin_batches_mod10_1200:1800.png)

The first epoch exhibited different "every 10th batch" periodicity.
</details>

### Census
Batch times (colored by [batch index] mod 10):
[![](img/census_batches_mod10.png)](img/census_batches_mod10.png)

Worst 10% of batches were ≈30-40x slower than average

Detail below shows "30x slower" batches repeated roughly every 10, but slipped by 1 every 40-50:

<details><summary>Example slow-batch-gap pattern: 10, 10, 10, 10, 9</summary>

[![](img/census_batches_mod10_1200:1800.png)](img/census_batches_mod10_1200:1800.png)
</details>

### MappedCollection
Batch times (colored by [batch index] mod **7**):
[![](img/mappedcollection_batches_mod7.png)](img/mappedcollection_batches_mod7.png)

MappedCollection had slow batches every 7 (as opposed to every 10 for the other two methods).

<details><summary>Detail: batch times repeating every 7</summary>

[![](img/mappedcollection_batches_mod7_1200:1800.png)](img/mappedcollection_batches_mod7_1200:1800.png)
</details>

[laminlabs/arrayloader-benchmarks]: https://github.com/laminlabs/arrayloader-benchmarks
[A large-scale benchmark]: https://lamin.ai/blog/arrayloader-benchmarks#a-large-scale-benchmark
