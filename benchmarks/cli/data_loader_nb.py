from functools import partial
from os import makedirs
from os.path import join, basename, dirname
from subprocess import check_call
from sys import stderr

from click import option, Choice
from papermill import execute_notebook
from utz import err, sh

from benchmarks.cli.base import cli
from benchmarks.data_loader.paths import NB_PATH, DEFAULT_DB_PATH, NB_DIR


@cli.command()
@option('-d', '--db-path', default=DEFAULT_DB_PATH, help='Path to "epochs" benchmark SQLite DB')
@option('-D', '--dataset-key', type=Choice(['2:7', '2:9', '2:14']), help="Filter to DB entries matching this URI")
@option('-h', '--host-key', type=Choice(['m3', 'ec2']), default='ec2', help='Filter to DB entries that were run on M3 Macbook vs. EC2 g4dn.8xlarge (default)')
@option('-o', '--out-dir', help='Directory (under -O/--out-root) to write the executed notebook – and associated plot data – to')
@option('-O', '--out-root', default=NB_DIR, help=f'Output "root" directory, default: {NB_DIR}')
@option('-s', '--since', help="Filter to DB entries run since this datetime (inclusive)")
@option('--s3', is_flag=True, help="Filter to DB entries run against S3")
def data_loader_nb(db_path, dataset_key, host_key, out_dir: str, out_root, since, s3):
    nb_path = NB_PATH
    out_dir = join(out_root, out_dir)
    out_nb_path = join(out_dir, basename(nb_path))

    if s3:
        uri_rgx = f'^s3://.*{dataset_key}'
    else:
        uri_rgx = f'^data/.*{dataset_key}'

    host_kwargs = {
        'ec2': dict(hostname_rgx='us-west-2', host='EC2 (g4dn.8xlarge)'),
        'm3': dict(hostname_rgx='m3', host='M3 Macbook')
    }[host_key]

    parameters = dict(
        db_path=db_path,
        **host_kwargs,
        out_dir=out_dir,
        show='png',
        since=since,
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
