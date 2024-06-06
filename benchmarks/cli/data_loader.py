from getpass import getuser
from os.path import join
from socket import gethostname
from subprocess import check_output, check_call, CalledProcessError
from typing import Optional, Type

import click
import pandas as pd
from click import option, argument

from benchmarks.benchmark import benchmark, Exp
from benchmarks.cli.base import cli
from benchmarks.paths import DATA_LOADER_STATS_DIR
from cellxgene_census.experimental.ml import ExperimentDataPipe, experiment_dataloader
from tiledbsoma import SOMATileDBContext, Experiment


TBL = 'epochs'
DEFAULT_DB_PATH = join(DATA_LOADER_STATS_DIR, 'epochs.db')


def parse_delimited_arg(delim: str = ',', choices: Optional[list[str]] = None, type: Optional[Type] = None, default=None):
    def _parse_delimited_arg(ctx, param, value):
        if value is None:
            return default
        values = value.split(delim)
        if type is not None:
            values = [type(v) for v in values]
        if choices is not None:
            for v in values:
                if v not in choices:
                    raise click.BadParameter(f"Invalid value: {v}")
        return values

    return _parse_delimited_arg


METHODS = ['np.array', 'scipy.coo', 'scipy.csr']


@cli.command()
@option('-b', '--batch-size', default=1024, type=int)
@option('-c', '--soma-chunk-size', 'soma_chunk_sizes', callback=parse_delimited_arg(type=int, default=[10_000]), help='Comma-delimited list of chunk sizes to test; default is [10_000]', default='10_000')
@option('-C', '--no-cuda-conversion', is_flag=True)
@option('-d', '--db-path', default=DEFAULT_DB_PATH, help=f'Insert a row in this SQLite database with the samples/sec and other -M/--metadata; defaults to {DEFAULT_DB_PATH}, disable with -D/--no-db')
@option('-D', '--no-db', is_flag=True, help=f"Don't insert timings into the default SQLite database ({DEFAULT_DB_PATH}).")
@option('-e', '--num-epochs', default=1, type=int)
@option('-m', '--method', 'methods', callback=parse_delimited_arg(choices=METHODS, default=METHODS), help=f'Comma-delimited list of matrix conversion methods to test; options: [{", ".join(METHODS)}], default is all')
@option('-n', '--shuffle-chunk-count', default=1, type=int)
@option('-g', '--gc-freq', default=10, type=int)
@option('-M', '--metadata', multiple=True, help='<key>=<value> pairs to attach to the record persisted to the -d/--database')
@option('-P', '--py-buffer-size', default=1024**3, type=int)
@option('-S', '--soma-buffer-size', default=1024**3, type=int)
@argument('uri')  # e.g. `data/census-benchmark_2:3`; `alb download -s2 -e3
def data_loader(
        batch_size,
        soma_chunk_sizes,
        db_path,
        no_db,
        no_cuda_conversion,
        num_epochs,
        shuffle_chunk_count,
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

    print(f"{soma_chunk_sizes=}, {methods=}")

    context = SOMATileDBContext(tiledb_config=tiledb_config)
    sha = check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    try:
        check_call(['git', 'diff', '--quiet', 'HEAD'])
        sha_str = sha
    except CalledProcessError:
        sha_str = f"{sha}-dirty"

    for method in methods:
        for soma_chunk_size in soma_chunk_sizes:
            metadata_dict = {
                'alb_start': pd.Timestamp.now(),
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
