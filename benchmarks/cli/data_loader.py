import click

from benchmarks.benchmark import benchmark, Exp, Results, Method
from benchmarks.cli.base import cli

from cellxgene_census.experimental.ml import ExperimentDataPipe, experiment_dataloader
from cellxgene_census.experimental.ml.pytorch import Fmt
from tiledbsoma import SOMATileDBContext, Experiment
from tiledbsoma.stats import profile, stats


@cli.command()
@click.option('-b', '--batch-size', default=1024, type=int)
@click.option('-c', '--soma-chunk-size', default=10_000, type=int)
@click.option('-C', '--no-cuda-conversion', is_flag=True)
@click.option('-e', '--num-epochs', default=1, type=int)
@click.option('-g', '--gc-freq', default=10, type=int)
@click.option('-P', '--py-buffer-size', default=1024**3, type=int)
@click.option('-s', '--output-scipy', count=True, help='0x: pyarrow (`.tables`), 1x: scipy coo (`.scipy(compress=False)`), 2x: scipy csr (`.scipy(compress=True)`)')
@click.option('-S', '--soma-buffer-size', default=1024**3, type=int)
@click.argument('uri')  # e.g. `data/census-benchmark_2:3`; `alb download -s2 -e3
def data_loader(batch_size, soma_chunk_size, no_cuda_conversion, num_epochs, gc_freq, py_buffer_size, output_scipy, soma_buffer_size, uri):
    tiledb_config = {
        "py.init_buffer_bytes": py_buffer_size,
        "soma.init_buffer_bytes": soma_buffer_size,
    }
    if output_scipy == 0:
        fmt: Fmt = 'arrow.coo'
    elif output_scipy == 1:
        fmt: Fmt = 'scipy.coo'
    elif output_scipy == 2:
        fmt: Fmt = 'scipy.csr'
    else:
        raise ValueError(f"Invalid output_scipy value: {output_scipy}")

    context = SOMATileDBContext(tiledb_config=tiledb_config)
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
        for epoch in range(num_epochs):
            with profile(f'benchmark-epoch{epoch}'):
                epoch = benchmark(
                    exp,
                    batch_size=batch_size,
                    gc_freq=gc_freq,
                    ensure_cuda=not no_cuda_conversion,
                )
            epochs.append(epoch)

        results = Results(
            census=Method('census', epochs),
        )
        exp_stats = datapipe.stats()
        checkpoints_df = exp_stats.checkpoints_df()
        print("Checkpoints total:")
        print(f"{checkpoints_df.sum()}s")
        print()

        timers_df, counters_df = stats.dfs
        print(f"Timers total: {timers_df['sum'].sum()}s")
        print(timers_df.groupby('name')['sum'].sum())
