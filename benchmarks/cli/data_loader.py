import re
from dataclasses import dataclass
from getpass import getuser
from os.path import exists
from socket import gethostname
from subprocess import check_output, check_call, CalledProcessError
from typing import Optional, Callable, Tuple

import click
import pandas as pd
from click import option, argument
from utz import err

from benchmarks.benchmark import benchmark, Exp
from benchmarks.cli.base import cli, slice_opts
from benchmarks.data_loader.paths import DEFAULT_PQT_PATH
from benchmarks.ec2 import ec2_instance_id, ec2_instance_type
from cellxgene_census.experimental.ml import ExperimentDataPipe, experiment_dataloader
from cellxgene_census.experimental.ml.pytorch import METHODS, Method
from tiledbsoma import SOMATileDBContext, Experiment


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

    CHUNKS_RGX = re.compile(r'(?:(?P<block_chunks>\d+)x)?(?P<chunk_size>\d+)')
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
                chunks_per_block=int(m.group('block_chunks') or 1),
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
                if block_chunks_start > block_chunks_stop:
                    reverse = True
                    block_chunks_start, block_chunks_stop = block_chunks_stop, block_chunks_start
                else:
                    reverse = False
                block_specs = [
                    BlockSpec.make(chunks_per_block=block_chunks, block_size=block_size)
                    for block_chunks in pows(block_chunks_start, block_chunks_stop, pow=2)
                ]
                return block_specs if not reverse else block_specs[::-1]
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

    def __repr__(self):
        return f"{self.chunks_per_block}x{self.chunk_size} ({self.block_size})"


def parse_method(s: str) -> Method:
    if s in METHODS:
        return s
    prefix_matches = [
        method
        for method in METHODS
        if method.startswith(s)
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    raise ValueError(f"Unrecognized 'method' string: {s}")


@cli.command()
@option('-b', '--block-specs', callback=lambda ctx, param, value: BlockSpec.parse(value), multiple=True, help='Block/Chunk sizes to test, e.g. "131072/[1,2048]", "2048x64"')
@option('-B', '--batch-size', default=1024, type=int)
@option('-C', '--no-cuda-conversion', is_flag=True)
@option('-d', '--db-path', default=DEFAULT_PQT_PATH, help=f'Append a row to this Parquet file for each epoch run, including samples/sec and other -M/--metadata; defaults to {DEFAULT_PQT_PATH}')
@option('-E', '--num-epochs', default=1, type=int)
@option('-g', '--gc-freq', default=10, type=int)
@option('-m', '--method', 'methods', callback=parse_delimited_arg(choices=METHODS, default=METHODS, fn=parse_method), help=f'Comma-delimited list of matrix conversion methods to test; options: [{", ".join(METHODS)}], default is all; unique prefixes accepted')
@option('-M', '--metadata', multiple=True, help='<key>=<value> pairs to attach to the record persisted to the -d/--database')
@option('-n', '--max-batches', type=int, default=0, help='Optional: exit after this many batches; 0 ⇒ no max')
@option('-P', '--py-buffer-size', default=1024**3, type=int)
@option('-q', '--quiet', count=True, help='1x: disable progress bar')
@option('-r', '--region', help="S3 region")
@option('-z', '--soma-buffer-size', default=1024**3, type=int)
@argument('uri', required=False)  # e.g. `data/census-benchmark_2:3`; `alb download -s2 -e3
@slice_opts
def data_loader(
        block_specs,
        batch_size,
        db_path,
        no_cuda_conversion,
        num_epochs,
        methods,
        gc_freq,
        metadata,
        max_batches,
        py_buffer_size,
        quiet,
        region,
        soma_buffer_size,
        uri,
        # slice_opts
        collection_id,
        census_uri,
        census_version,
        start,
        end,
        sorted_datasets,
        # slice_opts generates these, when reading+slicing directly from Census
        exp_fn=None,
        obs_query=None,
        var_query=None,
):
    """Benchmark loading batches into PyTorch, from a TileDB-SOMA experiment."""
    tiledb_config = {
        "py.init_buffer_bytes": py_buffer_size,
        "soma.init_buffer_bytes": soma_buffer_size,
    }
    if region:
        tiledb_config["vfs.s3.region"] = region

    err(f"{methods=}")
    err("Block specs:\n\t%s\n" % "\n\t".join(map(repr, block_specs)))

    context = SOMATileDBContext(tiledb_config=tiledb_config)
    sha = check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    try:
        check_call(['git', 'diff', '--quiet', 'HEAD'])
        sha_str = sha
    except CalledProcessError:
        sha_str = f"{sha}-dirty"

    alb_start_dt = pd.Timestamp.now()
    for block_spec in block_specs:
        for method in methods:
            err(f"Running {method=}, {block_spec=}")
            chunk_size = block_spec.chunk_size
            chunks_per_block = block_spec.chunks_per_block
            metadata_dict = {
                'alb_start_dt': alb_start_dt,
                'sha': sha_str,
                'user': getuser(),
                'hostname': gethostname(),
                'uri': uri,
                'method': method,
                'batch_size': batch_size,
                'max_batches': max_batches,
                'chunk_size': chunk_size,
                'chunks_per_block': chunks_per_block,
                'block_size': block_spec.block_size,
                'py_buffer_size': py_buffer_size,
                'soma_buffer_size': soma_buffer_size,
                'collection_id': collection_id,
                'census_uri': census_uri,
                'census_version': census_version,
                'start_idx': start,
                'end_idx': end,
                'sorted_datasets': sorted_datasets,
            }
            metadata_dict.update(**{
                k: v for k, v in
                (m.split('=', 1) for m in metadata)
            })
            instance_id = ec2_instance_id()
            if instance_id:
                metadata_dict['instance_id'] = instance_id
            instance_type = ec2_instance_type()
            if instance_type:
                metadata_dict['instance_type'] = instance_type
            if exp_fn:
                experiment = exp_fn()
            else:
                experiment = Experiment.open(uri, context=context)
            datapipe = ExperimentDataPipe(
                experiment,
                measurement_name="RNA",
                X_name="raw",
                batch_size=batch_size,
                shuffle=True,
                soma_chunk_size=chunk_size,
                shuffle_chunk_count=chunks_per_block,
                obs_query=obs_query,
                var_query=var_query,
                method=method,
                max_batches=max_batches,
            )
            loader = experiment_dataloader(datapipe)
            exp = Exp(datapipe, loader)

            epochs = []
            records = []
            for epoch_idx in range(num_epochs):
                start_dt = pd.Timestamp.now()
                epoch = benchmark(
                    exp,
                    batch_size=batch_size,
                    gc_freq=gc_freq,
                    ensure_cuda=not no_cuda_conversion,
                    max_batches=max_batches,
                    progress_bar=quiet < 1,
                )
                records.append(dict(
                    start_dt=start_dt,
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
            if exists(db_path):
                existing = pd.read_parquet(db_path)
                err(f"Appending {len(records_df)} records to {len(existing)} existing, at {db_path}")
                new_df = pd.concat([existing, records_df], ignore_index=True).reset_index(drop=True)
                new_df.to_parquet(db_path, index=False)
            else:
                err(f"Writing {len(records_df)} records to {db_path}")
                records_df.to_parquet(db_path, index=False)
            err(records_df)
