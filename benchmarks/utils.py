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
from os import makedirs
from os.path import exists, join, splitext
from re import fullmatch
from shutil import rmtree
from subprocess import check_call, check_output
from sys import stderr
from tempfile import TemporaryDirectory
from time import time
from typing import Literal, Protocol, Optional
from urllib.parse import urlparse

# 3rd party
import numpy as np
from numpy import nan
import pyarrow as pa
import pandas as pd
import requests
from tqdm import tqdm
from utz import err, silent

# Other local files
from benchmarks import census
from benchmarks.census import *
from benchmarks.plot import *
import cellxgene_census
from tiledbsoma.stats import *


def get_dataset_ids(_census, collection_id=COLLECTION_ID, profile=None):
    return census.get_dataset_ids(census=_census, collection_id=collection_id, profile=profile)


def get_region():
    """Return the region the current EC2 instance is running in.

    Adapted from https://stackoverflow.com/a/31336629/23555888.
    """
    r = requests.get('http://169.254.169.254/latest/meta-data/placement/availability-zone')
    r.raise_for_status()
    az = r.text
    return az[:-1]


def is_local(uri: str) -> bool:
    scheme = urlparse(uri).scheme
    return not scheme or scheme == 'file'
