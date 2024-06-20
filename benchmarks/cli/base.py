from functools import wraps
from inspect import getfullargspec

from click import group, option
from somacore import AxisQuery
from utz import err

import cellxgene_census
from benchmarks import COLLECTION_ID
from benchmarks.census import get_dataset_ids, axis_query

collection_id_opt = option('-c', '--collection-id', default=COLLECTION_ID, help=f"Census collection ID to slice datasets from; default: {COLLECTION_ID}")
census_uri_opt = option('-u', '--census-uri', help="Optional Census URI override, default is determined by -V/--census-version")
census_version_opt = option('-V', '--census-version', default="2023-12-15")

start_opt = option('-s', '--start', default=0, help='Slice datasets from `collection_id` starting from this index')
sorted_datasets_flag = option('-S', '--sorted-datasets', is_flag=True, help='Sort datasets (from `collection_id`) by `dataset_total_cell_count` before slicing')
end_opt = option('-e', '--end', type=int, help='Slice datasets from `collection_id` ending at this index')
n_vars_opt = option('-v', '--n-vars', default=20_000, help='Slice the first `n_vars` vars')


def slice_opts(fn):
    @collection_id_opt
    @end_opt
    @start_opt
    @sorted_datasets_flag
    @census_uri_opt
    @census_version_opt
    @n_vars_opt
    @wraps(fn)
    def _fn(*args, **kwargs):
        collection_id = kwargs['collection_id']
        census_uri = kwargs['census_uri']
        census_version = kwargs['census_version']
        start = kwargs['start']
        end = kwargs['end']
        sorted_datasets = kwargs['sorted_datasets']
        n_vars = kwargs['n_vars']
        spec = getfullargspec(fn)
        fn_kwargs = dict(**kwargs, query=None, obs_query=None, var_query=None)
        if start is not None or end is not None:
            census = cellxgene_census.open_soma(uri=census_uri, census_version=census_version)
            dataset_ids = get_dataset_ids(census, collection_id, sort_values='dataset_total_cell_count' if sorted_datasets else None)
            print(f'Found {len(dataset_ids)} total datasets: {dataset_ids[:10]}… slicing [{start},{end})')
            ds = dataset_ids[slice(start, end)]
            datasets_query = f'dataset_id in {ds}'
            if 'query' in spec.args:
                experiment = census["census_data"]["homo_sapiens"]
                fn_kwargs['query'] = axis_query(experiment, dataset_ids, start=start, end=end, n_vars=n_vars)
            else:
                def exp_fn():
                    census = cellxgene_census.open_soma(uri=census_uri, census_version=census_version)
                    return census["census_data"]["homo_sapiens"]

                fn_kwargs['exp_fn'] = exp_fn
                fn_kwargs['obs_query'] = AxisQuery(value_filter=datasets_query)
                fn_kwargs['var_query'] = AxisQuery(coords=(slice(n_vars - 1),)) if n_vars else None

        fn_kwargs = {
            k: v
            for k, v in fn_kwargs.items()
            if k in spec.args
        }
        return fn(*args, **fn_kwargs)
    return _fn


@group(context_settings=dict(max_content_width=120))
def cli():
    """Data-loading benchmarks for cellxgene-census and tiledbsoma."""
    pass
