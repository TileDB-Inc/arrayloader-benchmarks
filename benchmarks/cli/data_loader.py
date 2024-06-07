import json
import re
from dataclasses import dataclass, asdict
from getpass import getuser
from os.path import join
from socket import gethostname
from subprocess import check_output, check_call, CalledProcessError
from sys import stderr
from typing import Optional, Callable, Tuple

import click
import pandas as pd
from cellxgene_census.experimental.ml.pytorch import METHODS
from click import option, argument
from utz import err

from benchmarks.benchmark import benchmark, Exp
from benchmarks.cli.base import cli
from benchmarks.paths import DATA_LOADER_STATS_DIR
from cellxgene_census.experimental.ml import ExperimentDataPipe, experiment_dataloader
from tiledbsoma import SOMATileDBContext, Experiment


TBL = 'epochs'
DEFAULT_DB_PATH = join(DATA_LOADER_STATS_DIR, 'epochs.db')


def parse_delimited_arg(
        delim: str = ',',
        choices: Optional[list[str]] = None,
        fn: Optional[Callable] = None,
        flatten: bool = True,
        default=None,
):
    def _parse_delimited_arg(ctx, param, value):
        if value is None:
            return default
        values = value.split(delim)
        if fn is not None:
            values0 = values
            values = []
            for v0 in values0:
                v = fn(v0)
                if flatten and isinstance(v, list):
                    values.extend(v)
        if choices is not None:
            for v in values:
                if v not in choices:
                    raise click.BadParameter(f"Invalid value: {v}")
        return values

    return _parse_delimited_arg


def pows(start: int, stop: int, pow: int = 2):
    rv = []
    while start <= stop:
        rv.append(start)
        start *= pow
    return rv


def to_list(n: int | Tuple[int, int]) -> list[int]:
    if isinstance(n, int):
        return [n]
    elif len(n) == 2:
        return pows(n[0], n[1], pow=2)
    else:
        raise ValueError(f"Unrecognized arg: {n}")


@dataclass
class BlockSpec:
    chunks_per_block: int
    chunk_size: int
    block_size: int  # chunk_size * chunks_per_block

    CHUNKS_RGX = re.compile(r'(?P<block_chunks>\d+)x(?P<chunk_size>\d+)')
    CHUNKS_PER_BLOCK_RGX = re.compile(r'(?P<block_size>\d+) */ *(?:(?P<block_chunks>\d+)|\[(?P<block_chunks_start>\d+), *(?P<block_chunks_stop>\d+)])')

    @classmethod
    def parse(cls, s: str | tuple[str]) -> list['BlockSpec']:
        if isinstance(s, tuple):
            return [
                block_spec
                for block_specs in s
                for block_spec in cls.parse(block_specs)
            ]
        m = cls.CHUNKS_RGX.fullmatch(s)
        if m is not None:
            return [ BlockSpec.make(
                chunks_per_block=int(m.group('block_chunks')),
                chunk_size=int(m.group('chunk_size')),
            ) ]
        m = cls.CHUNKS_PER_BLOCK_RGX.fullmatch(s)
        if m is not None:
            block_chunks = m.group('block_chunks')
            block_size = int(m.group('block_size'))
            if block_chunks is not None:
                return [ BlockSpec.make(chunks_per_block=int(block_chunks), block_size=block_size) ]
            else:
                block_chunks_start = int(m.group('block_chunks_start'))
                block_chunks_stop = int(m.group('block_chunks_stop'))
                return [
                    BlockSpec.make(chunks_per_block=block_chunks, block_size=block_size)
                    for block_chunks in pows(block_chunks_start, block_chunks_stop, pow=2)
                ]
        raise ValueError(f"Invalid block spec: {s}")

    @staticmethod
    def make(chunks_per_block=None, chunk_size=None, block_size=None) -> 'BlockSpec':
        num_nones = sum(1 for v in (chunks_per_block, chunk_size, block_size) if v is None)
        if num_nones > 1:
            raise ValueError("Must provide at least 2 of {chunks_per_block, chunk_size, block_size}")
        if chunks_per_block is None:
            if block_size % chunk_size != 0:
                raise ValueError(f"block_size {block_size} must be a multiple of chunk_size {chunk_size}")
            chunks_per_block = block_size // chunk_size
        elif chunk_size is None:
            if block_size % chunks_per_block != 0:
                raise ValueError(f"block_size {block_size} must be a multiple of chunks_per_block {chunks_per_block}")
            chunk_size = block_size // chunks_per_block
        elif block_size is None:
            block_size = chunks_per_block * chunk_size
        else:
            if block_size != chunks_per_block * chunk_size:
                raise ValueError(f"block_size {block_size} != chunks_per_block {chunks_per_block} * chunk_size {chunk_size}")
        return BlockSpec(chunks_per_block=chunks_per_block, chunk_size=chunk_size, block_size=block_size)


@cli.command()
@option('-b', '--block-specs', callback=lambda ctx, param, value: BlockSpec.parse(value), multiple=True, help='Block/Chunk sizes to test, e.g. "131072/[1,2048]", "2048x64"')
@option('-B', '--batch-size', default=1024, type=int)
@option('-C', '--no-cuda-conversion', is_flag=True)
@option('-d', '--db-path', default=DEFAULT_DB_PATH, help=f'Insert a row in this SQLite database with the samples/sec and other -M/--metadata; defaults to {DEFAULT_DB_PATH}, disable with -D/--no-db')
@option('-D', '--no-db', is_flag=True, help=f"Don't insert timings into the default SQLite database ({DEFAULT_DB_PATH}).")
@option('-e', '--num-epochs', default=1, type=int)
@option('-m', '--method', 'methods', callback=parse_delimited_arg(choices=METHODS, default=METHODS), help=f'Comma-delimited list of matrix conversion methods to test; options: [{", ".join(METHODS)}], default is all')
@option('-g', '--gc-freq', default=10, type=int)
@option('-M', '--metadata', multiple=True, help='<key>=<value> pairs to attach to the record persisted to the -d/--database')
@option('-P', '--py-buffer-size', default=1024**3, type=int)
@option('-S', '--soma-buffer-size', default=1024**3, type=int)
@argument('uri')  # e.g. `data/census-benchmark_2:3`; `alb download -s2 -e3
def data_loader(
        block_specs,
        batch_size,
        db_path,
        no_db,
        no_cuda_conversion,
        num_epochs,
        methods,
        gc_freq,
        metadata,
        py_buffer_size,
        soma_buffer_size,
        uri,
):
    """Benchmark loading batches into PyTorch, from a TileDB-SOMA experiment."""
    tiledb_config = {
        "py.init_buffer_bytes": py_buffer_size,
        "soma.init_buffer_bytes": soma_buffer_size,
    }

    err(f"{methods=}")
    err("Block specs:")
    json.dump(list(map(asdict, block_specs)), stderr, indent=2)
    err()

    context = SOMATileDBContext(tiledb_config=tiledb_config)
    sha = check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    try:
        check_call(['git', 'diff', '--quiet', 'HEAD'])
        sha_str = sha
    except CalledProcessError:
        sha_str = f"{sha}-dirty"

    alb_start = pd.Timestamp.now()
    for method in methods:
        for block_spec in block_specs:
            soma_chunk_size = block_spec.chunk_size
            shuffle_chunk_count = block_spec.chunks_per_block
            metadata_dict = {
                'alb_start': alb_start,
                'sha': sha_str,
                'user': getuser(),
                'hostname': gethostname(),
                'uri': uri,
                'method': method,
                'batch_size': batch_size,
                'soma_chunk_size': soma_chunk_size,
                'shuffle_chunk_count': shuffle_chunk_count,
                'py_buffer_size': py_buffer_size,
                'soma_buffer_size': soma_buffer_size,
            }
            metadata_dict.update(**{
                k: v for k, v in
                (m.split('=', 1) for m in metadata)
            })
            with Experiment.open(uri, context=context) as experiment:
                datapipe = ExperimentDataPipe(
                    experiment,
                    measurement_name="RNA",
                    X_name="raw",
                    batch_size=batch_size,
                    shuffle=True,
                    soma_chunk_size=soma_chunk_size,
                    shuffle_chunk_count=shuffle_chunk_count,
                    method=method,
                )

                loader = experiment_dataloader(datapipe)
                exp = Exp(datapipe, loader)

                epochs = []
                records = []
                for epoch_idx in range(num_epochs):
                    start = pd.Timestamp.now()
                    epoch = benchmark(
                        exp,
                        batch_size=batch_size,
                        gc_freq=gc_freq,
                        ensure_cuda=not no_cuda_conversion,
                    )
                    records.append(dict(
                        start=start,
                        epoch=epoch_idx,
                        n_rows=epoch.n_rows,
                        n_cols=epoch.n_cols,
                        elapsed=epoch.elapsed,
                        gc=epoch.gc,
                        max_mem=datapipe.max_process_mem_usage_bytes,
                        **metadata_dict,
                    ))
                    epochs.append(epoch_idx)

                records_df = pd.DataFrame(records)
                if not no_db:
                    db_uri = f"sqlite:///{db_path}"
                    records_df.to_sql(TBL, db_uri, if_exists='append', index=False)

                print(records_df)
