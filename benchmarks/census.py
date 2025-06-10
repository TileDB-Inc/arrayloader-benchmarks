from contextlib import nullcontext
from os import makedirs
from os.path import join, exists
from shutil import rmtree
from typing import Optional

import pandas as pd
import pyarrow as pa
from utz import err

from benchmarks import COLLECTION_ID
from somacore import ExperimentAxisQuery, AxisQuery
import tiledbsoma
from tiledbsoma import Experiment, Measurement
from tiledbsoma.stats import tiledbsoma_stats_as_py as stats


def get_datasets_df(census, collection_id=COLLECTION_ID, profile=None, sort_values=None) -> pd.DataFrame:
    with stats.collect(profile) if profile else nullcontext():
        df = (
            census["census_info"]["datasets"]
            .read(value_filter=f"collection_id == '{collection_id}'")
            .concat()
            .to_pandas()
        )
    if sort_values:
        df = df.sort_values(sort_values)
    return df


def get_dataset_ids(*args, **kwargs):
    df = get_datasets_df(*args, **kwargs)
    return (
        df
        .dataset_id
        .tolist()
    )


def subset_census(query: ExperimentAxisQuery, output_base_dir: str) -> None:
    """
    Subset the census cube to the given query, returning a new cube.

    Adapted from https://github.com/chanzuckerberg/cellxgene-census/blob/atol/memento/epic/tools/models/memento/tests/fixtures/census_fixture.py#L10), see also https://github.com/chanzuckerberg/cellxgene-census/issues/1082.
    """
    makedirs(output_base_dir, exist_ok=True)
    with Experiment.create(uri=output_base_dir) as exp_subset:
        x_data = query.X(layer_name="raw").tables().concat()

        obs_data = query.obs().concat()
        # remove obs rows with no X data
        x_soma_dim_0_unique = pa.Table.from_arrays([x_data["soma_dim_0"].unique()], names=["soma_dim_0"])
        obs_data = obs_data.join(x_soma_dim_0_unique, keys="soma_joinid", right_keys="soma_dim_0", join_type="inner")
        obs = tiledbsoma.DataFrame.create(join(output_base_dir, "obs"), schema=obs_data.schema)
        obs.write(obs_data)
        exp_subset.set("obs", obs)

        ms = exp_subset.add_new_collection("ms")
        rna = ms.add_new_collection("RNA", Measurement)

        var_data = query.var().concat()
        var = rna.add_new_dataframe("var", schema=var_data.schema)
        var.write(var_data)

        x_type = x_data.schema.field_by_name("soma_data").type
        rna.add_new_collection("X")
        rna["X"].add_new_sparse_ndarray("raw", type=x_type, shape=(None, None))
        rna.X["raw"].write(x_data)


def axis_query(
        exp: Experiment,
        datasets: list[str],
        start: Optional[int] = None,
        end: Optional[int] = None,
        n_vars: Optional[int] = None,
) -> ExperimentAxisQuery:
    ds = datasets[slice(start, end)]
    err(f"Downloading {len(ds)} datasets:\n\t%s" % "\n\t".join(ds))
    datasets_query = f'dataset_id in {ds}'
    obs_query = AxisQuery(value_filter=datasets_query)
    var_query = AxisQuery(coords=(slice(n_vars - 1),)) if n_vars else None
    return exp.axis_query(
        "RNA",
        obs_query=obs_query,
        var_query=var_query,
    )


def download_datasets(
        query: ExperimentAxisQuery,
        out_dir: str,
        rm: bool = True,
):
    if exists(out_dir):
        if rm:
            err(f"Removing {out_dir}")
            rmtree(out_dir)
        else:
            raise RuntimeError(f"Directory {out_dir} exists and rm=False")

    subset_census(query, out_dir)
