from subprocess import check_output

from click import option
from utz import err

from benchmarks.census import download_datasets
from benchmarks.cli.base import cli, slice_opts
from benchmarks.cli.dataset_slice import DatasetSlice

DEFAULT_OUT_ROOT = "data"


@cli.command()
@option('-d', '--out-root', default=DEFAULT_OUT_ROOT, help=f"Directory to save sliced data into; default: {DEFAULT_OUT_ROOT}")
@option('-f', '--force', is_flag=True, help='rm existing out_dir before writing')
@option('-n', '--out-dir-name', 'out_dir', help="Basename under -d/--out-root to save sliced subset to; default: `census-benchmark_{start}:{end}`")
@slice_opts
def download(query, out_root, force, end, out_dir, start, sorted_datasets):
    """Slice and export cellxgene-census datasets to a local directory."""
    if out_dir is None:
        dataset_slice = DatasetSlice(start=start, end=end, sorted_datasets=sorted_datasets)
        out_dir = f'{out_root}/census-benchmark{dataset_slice}'
    else:
        out_dir = f"{out_root}/{out_dir}"
        err(f"Downloading to {out_dir}")

    download_datasets(query, out_dir, rm=force)
    h_size = check_output(['du', '-sh', out_dir]).decode().split('\t')[0]
    print(f"{out_dir}: {h_size}")
