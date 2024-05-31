from getpass import getuser
from os.path import join
from socket import gethostname
from subprocess import check_output, check_call, CalledProcessError

import click
import pandas as pd

from benchmarks.benchmark import benchmark, Exp
from benchmarks.cli.base import cli
from benchmarks.paths import DATA_LOADER_STATS_DIR
from cellxgene_census.experimental.ml import ExperimentDataPipe, experiment_dataloader
from cellxgene_census.experimental.ml.pytorch import Fmt
from tiledbsoma import SOMATileDBContext, Experiment
from tiledbsoma.stats import profile

TBL = 'epochs'
DEFAULT_DB_PATH = join(DATA_LOADER_STATS_DIR, 'epochs.db')


@cli.command()
@click.option('-b', '--batch-size', default=1024, type=int)
@click.option('-c', '--soma-chunk-size', default=10_000, type=int)
@click.option('-C', '--no-cuda-conversion', is_flag=True)
@click.option('-d', '--db-path', default=DEFAULT_DB_PATH, help=f'Insert a row in this SQLite database with the samples/sec and other -m/--metadata; defaults to {DEFAULT_DB_PATH}, disable with -D/--no-db')
@click.option('-D', '--no-db', is_flag=True, help=f"Don't insert timings into the default SQLite database ({DEFAULT_DB_PATH}).")
@click.option('-e', '--num-epochs', default=1, type=int)
@click.option('-g', '--gc-freq', default=10, type=int)
@click.option('-m', '--metadata', multiple=True, help='<key>=<value> pairs to attach to the record persisted to the -d/--database')
@click.option('-P', '--py-buffer-size', default=1024**3, type=int)
@click.option('-s', '--output-scipy', count=True, help='0x: pyarrow (`.tables`), 1x: scipy coo (`.scipy(compress=False)`), 2x: scipy csr (`.scipy(compress=True)`)')
@click.option('-S', '--soma-buffer-size', default=1024**3, type=int)
@click.argument('uri')  # e.g. `data/census-benchmark_2:3`; `alb download -s2 -e3
def data_loader(
        batch_size,
        soma_chunk_size,
        db_path,
        no_db,
        no_cuda_conversion,
        num_epochs,
        gc_freq,
        metadata,
        py_buffer_size,
        output_scipy,
        soma_buffer_size,
        uri,
):
    """Benchmark loading batches into PyTorch, from a TileDB-SOMA experiment."""
    tiledb_config = {
        "py.init_buffer_bytes": py_buffer_size,
        "soma.init_buffer_bytes": soma_buffer_size,
    }
    if output_scipy == 0:
        fmt: Fmt = 'np.array'
    elif output_scipy == 1:
        fmt: Fmt = 'scipy.coo'
    elif output_scipy == 2:
        fmt: Fmt = 'scipy.csr'
    else:
        raise ValueError(f"Invalid output_scipy value: {output_scipy}")

    context = SOMATileDBContext(tiledb_config=tiledb_config)
    sha = check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    try:
        check_call(['git', 'diff', '--quiet', 'HEAD'])
        sha_str = sha
    except CalledProcessError:
        sha_str = f"{sha}-dirty"
    metadata_dict = {
        'alb_start': pd.Timestamp.now(),
        'sha': sha_str,
        'user': getuser(),
        'hostname': gethostname(),
        'uri': uri,
        'fmt': fmt,
        'batch_size': batch_size,
        'soma_chunk_size': soma_chunk_size,
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
            fmt=fmt,
        )

        loader = experiment_dataloader(datapipe)
        exp = Exp(datapipe, loader)

        epochs = []
        records = []
        for epoch_idx in range(num_epochs):
            start = pd.Timestamp.now()
            with profile(f'benchmark-epoch{epoch_idx}'):
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
                elapsed=epoch.elapsed,
                gc=epoch.gc,
                **metadata_dict,
            ))
            epochs.append(epoch_idx)

        records_df = pd.DataFrame(records)
        if not no_db:
            db_uri = f"sqlite:///{db_path}"
            records_df.to_sql(TBL, db_uri, if_exists='append', index=False)

        print(records_df)
