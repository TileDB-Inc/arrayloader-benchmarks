# Helper for wildcard-importing common utilities in notebooks:
#
# ```python
# from utils import *
# ```

# Standard library
from contextlib import redirect_stdout, contextmanager, nullcontext
from dataclasses import dataclass, asdict, field
import gc
import json
from math import log10
import os
from os.path import exists, join, splitext
from re import fullmatch
from shutil import rmtree
from subprocess import check_call, check_output
from sys import stderr
from tempfile import TemporaryDirectory
from time import time
from typing import Literal, Protocol, Optional

# 3rd party
import numpy as np
from numpy import nan
import pyarrow as pa
import pandas as pd
import requests
from tqdm import tqdm

# Other local files
from census import *
from err import *
from plot import *
from stats import *

stats = Stats()
profile = stats.collect
tdb = stats.tdb
tdbs = stats.tdbs


collection_id = '283d65eb-dd53-496d-adb7-7570c7caa443'


def get_datasets(census, collection_id=collection_id, profile=None):
    with stats.collect(profile) if profile else nullcontext():
        return (
            census["census_info"]["datasets"]
            .read(
                column_names=["dataset_id"],
                value_filter=f"collection_id == '{collection_id}'",
            )
            .concat()
            .to_pandas()
            ["dataset_id"]
            .tolist()
        )


def get_region():
    """Return the region the current EC2 instance is running in.

    Adapted from https://stackoverflow.com/a/31336629/23555888.
    """
    r = requests.get('http://169.254.169.254/latest/meta-data/placement/availability-zone')
    r.raise_for_status()
    az = r.text
    return az[:-1]
