import click

import tiledbsoma as soma
import numpy as np
import time


#X_URI = "s3://cellxgene-census-public-us-west-2/cell-census/2023-12-15/soma/census_data/homo_sapiens/ms/RNA/X/raw"
# X_URI = 'data/census-benchmark_2:3/ms/RNA/X/raw'

DEFAULT_CONFIG = {
    "py.init_buffer_bytes": 1 * 1024**3,
    "soma.init_buffer_bytes": 1 * 1024**3,
    # S3 requests should not be signed, since we want to allow anonymous access
    "vfs.s3.no_sign_request": "true",
    "vfs.s3.region": "us-west-2",
}

# CHUNK_SIZE = 10_000
# OBS_SPAN = 20_000
# VAR_SLICE = slice(0, 100)


def read_table(X, obs_joinids, var_slice):
    # this should be fastest
    total_read = 0
    for tbl in X.read(coords=(obs_joinids, var_slice)).tables():
        # print(len(tbl))
        # print(repr(tbl))
        total_read += len(tbl)
    print(f"Total read_table: {total_read}")


def read_blockwise_table(X, obs_joinids, soma_chunk, var_slice):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        tbl, _ = next(
            X.read(coords=(chunk_obs_ids, var_slice))
            .blockwise(axis=0, size=len(chunk_obs_ids), eager=False)
            .tables()
        )
        print(len(tbl))
        # print(repr(tbl))
        total_read += len(tbl)
    print(f"Total read_blockwise_table: {total_read}")


def read_blockwise_scipy_coo(X, obs_joinids, soma_chunk, var_slice):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        coo, _ = next(
            X.read(coords=(chunk_obs_ids, var_slice))
            .blockwise(axis=0, size=len(chunk_obs_ids), eager=False)
            .scipy(compress=False)
        )
        print(repr(coo))
        total_read += coo.nnz
    print(f"Total read_blockwise_scipy_coo: {total_read}")


def read_blockwise_scipy_csr(X, obs_joinids, soma_chunk, var_slice):
    total_read = 0
    for idx in range(0, len(obs_joinids), soma_chunk):
        chunk_obs_ids = obs_joinids[idx : idx + soma_chunk]
        csr, _ = next(
            X.read(coords=(chunk_obs_ids, var_slice))
            .blockwise(axis=0, size=len(chunk_obs_ids), eager=False)
            .scipy(compress=True)
        )
        print(repr(csr))
        total_read += csr.nnz
    print(f"Total read_blockwise_scipy_csr: {total_read}")


@click.command()
@click.option('-c', '--soma-chunk', default=10_000, type=int)
@click.option('-s', '--shuffle', count=True, help='1x: chunk shuffle, 2x: global shuffle')
@click.option('-v', '--vars', default=20_000, type=int)
@click.argument('uri')  # 'data/census-benchmark_2:3'
def main(soma_chunk, shuffle, vars, uri):
    var_slice = slice(0, vars - 1)
    kwargs = dict(soma_chunk=soma_chunk, var_slice=var_slice)
    with soma.open(f'{uri}/obs') as obs:
        df = obs.read(column_names=['soma_joinid']).concat().to_pandas()
    obs_joinids = df.soma_joinid.to_numpy()

    if shuffle == 1:
        for idx in range(0, len(obs_joinids), soma_chunk):
            np.random.default_rng().shuffle(obs_joinids[idx: idx + soma_chunk])
    elif shuffle == 2:
        np.random.default_rng().shuffle(obs_joinids)

    context = soma.SOMATileDBContext(tiledb_config=DEFAULT_CONFIG)
    with soma.open(f'{uri}/ms/RNA/X/raw', context=context) as X:

        t = time.perf_counter()
        read_table(X, obs_joinids, var_slice=var_slice)
        print(f"read_table: {time.perf_counter() - t}")

        t = time.perf_counter()
        read_blockwise_table(X, obs_joinids, **kwargs)
        print(f"read_blockwise_table: {time.perf_counter() - t}")

        t = time.perf_counter()
        read_blockwise_scipy_coo(X, obs_joinids, **kwargs)
        print(f"read_blockwise_scipy_coo: {time.perf_counter() - t}")

        t = time.perf_counter()
        read_blockwise_scipy_csr(X, obs_joinids, **kwargs)
        print(f"read_blockwise_scipy_csr: {time.perf_counter() - t}")


if __name__ == "__main__":
    main()