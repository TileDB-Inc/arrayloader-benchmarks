from benchmarks import err
from benchmarks.cli.base import cli

import click

import tiledbsoma as soma
import numpy as np
import time

from benchmarks.err import silent


def read_table(X, obs_joinids, soma_chunk, var_slice, log):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        tbl = next(X.read(coords=(chunk_obs_ids, var_slice)).tables())
        n = len(tbl)
        log(f"read_table: {n}")
        total_read += n
    log(f"read_table total: {total_read}")
    return total_read


def read_blockwise_table(X, obs_joinids, soma_chunk, var_slice, log):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        tbl, _ = next(
            X.read(coords=(chunk_obs_ids, var_slice))
            .blockwise(axis=0, size=len(chunk_obs_ids), eager=False)
            .tables()
        )
        n = len(tbl)
        log(f"read_blockwise_table: {n}")
        total_read += n
    log(f"read_blockwise_table total: {total_read}")
    return total_read


def read_blockwise_scipy_coo(X, obs_joinids, soma_chunk, var_slice, log):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        coo, _ = next(
            X.read(coords=(chunk_obs_ids, var_slice))
            .blockwise(axis=0, size=len(chunk_obs_ids), eager=False)
            .scipy(compress=False)
        )
        arr_str = repr(coo).replace('\n', '')
        log(f"read_blockwise_scipy_coo: {arr_str}")
        total_read += coo.nnz
    log(f"read_blockwise_scipy_coo total: {total_read}")
    return total_read


def read_blockwise_scipy_csr(X, obs_joinids, soma_chunk, var_slice, log):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        csr, _ = next(
            X.read(coords=(chunk_obs_ids, var_slice))
            .blockwise(axis=0, size=len(chunk_obs_ids), eager=False)
            .scipy(compress=True)
        )
        arr_str = repr(csr).replace('\n', '')
        log(f"read_blockwise_scipy_csr: {arr_str}")
        total_read += csr.nnz
    log(f"read_blockwise_scipy_csr total: {total_read}")
    return total_read


@cli.command()
@click.option('-c', '--soma-chunk', default=10_000, type=int)
@click.option('-P', '--py-buffer-size', default=1024**3, type=int)
@click.option('-r', '--rng-seed', type=int)
@click.option('-s', '--shuffle', count=True, help='1x: chunk shuffle, 2x: global shuffle')
@click.option('-S', '--soma-buffer-size', default=1024**3, type=int)
@click.option('-v', '--verbose', is_flag=True, help='Print stats about each chunk read to stderr')
@click.option('-V', '--n_vars', default=20_000, type=int)
@click.argument('uri')  # e.g. `data/census-benchmark_2:3`; `alb download -s2 -e3
def benchmark(soma_chunk, py_buffer_size, rng_seed, shuffle, soma_buffer_size, n_vars, verbose, uri):
    var_slice = slice(0, n_vars - 1)
    with soma.open(f'{uri}/obs') as obs:
        df = obs.read(column_names=['soma_joinid']).concat().to_pandas()
    obs_joinids = df.soma_joinid.to_numpy()

    if shuffle == 1:
        for idx in range(0, len(obs_joinids), soma_chunk):
            np.random.default_rng(seed=rng_seed).shuffle(obs_joinids[idx: idx + soma_chunk])
    elif shuffle == 2:
        np.random.default_rng(seed=rng_seed).shuffle(obs_joinids)

    tiledb_config = {
        "py.init_buffer_bytes": py_buffer_size,
        "soma.init_buffer_bytes": soma_buffer_size,
    }

    if verbose:
        log = err
    else:
        log = silent

    context = soma.SOMATileDBContext(tiledb_config=tiledb_config)
    total_read = None
    with soma.open(f'{uri}/ms/RNA/X/raw', context=context) as X:
        for fn in [
            read_table,
            read_blockwise_table,
            read_blockwise_scipy_coo,
            read_blockwise_scipy_csr,
        ]:
            name = fn.__name__
            t = time.perf_counter()
            total = fn(X, obs_joinids, soma_chunk=soma_chunk, var_slice=var_slice, log=log)
            if total_read is not None and total != total_read:
                raise ValueError(f"{name} didn't read expected/previous number of elems: {total} != {total_read}")
            total_read = total
            print(f"{name} elapsed: {time.perf_counter() - t:.2f}s")
