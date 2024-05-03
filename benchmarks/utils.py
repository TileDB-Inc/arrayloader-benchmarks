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

# Other local files
from benchmarks import census
from benchmarks.census import *
from benchmarks.err import *
from benchmarks.plot import *
from tiledbsoma.stats import *


collection_id = '283d65eb-dd53-496d-adb7-7570c7caa443'


def get_datasets(_census, collection_id=collection_id, profile=None):
    return census.get_datasets(census=_census, collection_id=collection_id, profile=profile)


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
