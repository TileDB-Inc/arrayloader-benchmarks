from subprocess import check_output

from click import option

from benchmarks import err
from benchmarks.cli.base import cli

import cellxgene_census
from benchmarks.census import download_datasets, get_datasets


@cli.command()
@option('-c', '--collection-id', default='283d65eb-dd53-496d-adb7-7570c7caa443')
@option('-d', '--out-root', default="data")
@option('-e', '--end', default=7, help='Slice datasets from `collection_id` ending at this index')
@option('-f', '--force', is_flag=True, help='rm existing out_dir before writing')
@option('-n', '--out-dir-name', 'out_dir', default=None)
@option('-s', '--start', default=2, help='Slice datasets from `collection_id` starting from this index')
@option('-u', '--census-uri')
@option('-v', '--n-vars', default=20_000, help='Slice the first `n_vars` vars')
@option('-V', '--census-version', default="2023-12-15")
def download(collection_id, out_root, force, end, out_dir, start, census_uri, n_vars, census_version):
    if out_dir is None:
        suffix = "" if start is None and end is None else f"_{start or ''}:{end or ''}"
        out_dir = f'{out_root}/census-benchmark{suffix}'
    else:
        out_dir = f"{out_root}/{out_dir}"
        err(f"Downloading to {out_dir}")

    census = cellxgene_census.open_soma(uri=census_uri, census_version=census_version)
    datasets = get_datasets(census, collection_id)
    print(f'Found {len(datasets)} total datasets: {datasets[:10]}')
    experiment = census["census_data"]["homo_sapiens"]
    download_datasets(experiment, datasets, out_dir, start=start, end=end, n_vars=n_vars, rm=force)
    h_size = check_output(['du', '-sh', out_dir]).decode().split('\t')[0]
    print(f"{out_dir}: {h_size}")
