from os import makedirs
from os.path import join, basename, dirname

from click import option, argument
from papermill import execute_notebook
from utz import err, sh

from benchmarks.cli.base import cli
from benchmarks.cli.dataset_slice import DatasetSlice
from benchmarks.data_loader.paths import NB_PATH, NB_DIR, DEFAULT_PQT_PATH


@cli.command()
@option('-D', '--dataset-slice', callback=lambda ctx, param, value: DatasetSlice.parse(value) if value else None, help="Filter to DB entries matching this URI")
@option('-h', '--hostname-rgx', help='Filter to DB entries matching this hostname regex')
@option('-i', '--instance-type', help='Optional: filter to DB entries run on this EC2 `instance_type`')
@option('-n', '--max-batches', type=int, default=0, help='Optional: filter to DB entries with this `max_batch` set')
@option('-o', '--out-dir', help='Directory (under -O/--out-root) to write the executed notebook – and associated plot data – to')
@option('-O', '--out-root', default=NB_DIR, help=f'Output "root" directory, default: {NB_DIR}')
@option('-s', '--since', help="Filter to DB entries run since this datetime (inclusive)")
@option('--s3/--no-s3', is_flag=True, default=None, help="If set, filter to DB entries run against S3, or run locally")
@argument('db_path', default=DEFAULT_PQT_PATH)
def data_loader_nb(db_path, dataset_slice: DatasetSlice, hostname_rgx, instance_type, max_batches, out_dir: str, out_root, since, s3):
    nb_path = NB_PATH
    if not out_dir:
        if dataset_slice:
            out_dir = f'{dataset_slice}'
            if max_batches:
                out_dir += f'_{max_batches}'
        else:
            raise ValueError('Must provide -o/--out-dir or -d/--dataset-slice')
    out_dir = join(out_root, out_dir)
    out_nb_path = join(out_dir, basename(nb_path))

    if s3 is True:
        uri_rgx = f'^s3://.*{dataset_slice}'
    elif s3 is False:
        uri_rgx = f'^data/.*{dataset_slice}'
    else:
        uri_rgx = None

    parameters = dict(
        db_path=db_path,
        hostname_rgx=hostname_rgx,
        instance_type=instance_type,
        out_dir=out_dir,
        show='png',
        max_batches=max_batches,
        since=since,
        sorted_datasets=dataset_slice.sorted_datasets,
        start_idx=dataset_slice.start,
        end_idx=dataset_slice.end,
        uri_rgx=uri_rgx,
    )
    err(f"Running papermill: {nb_path} {out_nb_path}")
    err(f"{parameters=}")
    makedirs(dirname(out_nb_path), exist_ok=True)
    execute_notebook(
        nb_path,
        out_nb_path,
        parameters=parameters,
    )
    sh('juq', 'papermill-clean', '-i', out_nb_path)
