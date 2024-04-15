from contextlib import redirect_stdout, contextmanager
from dataclasses import dataclass, asdict, field
import gc
import json
from math import log10
import numpy as np
from numpy import nan
import os
from os.path import exists, join, splitext
from re import fullmatch
from shutil import rmtree
from subprocess import check_call
from sys import stderr
from tempfile import TemporaryDirectory
from time import time

from tiledbsoma import (
    tiledbsoma_stats_enable as stats_enable,
    tiledbsoma_stats_disable as stats_disable,
    tiledbsoma_stats_reset as stats_reset,
    tiledbsoma_stats_dump as stats_dump,
)
from tqdm import tqdm
from typing import Literal, Protocol, Optional

import pyarrow as pa
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import Figure
from plotly.subplots import make_subplots
default_colors = plotly.colors.DEFAULT_PLOTLY_COLORS

from IPython.display import Image, Markdown


def err(*args):
    print(*args, file=stderr)


@contextmanager
def collect_stats(*args):
    stats_reset()
    stats_enable()
    try:
        yield
    finally:
        stats_disable()
        if args:
            cur_stats = get_stats()
            n = len(args)
            if n == 1:
                arr = args[0]
                arr.append(cur_stats)
            elif n == 2:
                name, obj = args
                if 'name' in obj:
                    raise ValueError(f'Name {name} already exists in stats obj')
                obj[name] = cur_stats
            else:
                err(f"Unrecognized stats args (expected ``(Sequence,)`` or ``(str, dict)``): {args}")
                return


def stats_collector():
    stats = {}

    def collect(name):
        return collect_stats(name, stats)

    return stats, collect


def get_stats(reset: bool = False):
    with TemporaryDirectory() as tmp_dir:
        tmp_path = join(tmp_dir, 'stats.txt')
        with open(tmp_path, 'w') as f:
            with redirect_stdout(f):
                stats_dump()
        with open(tmp_path, 'r') as f:
            first, *lines = f.readlines()
            first = first.rstrip('\n')
            if not fullmatch(r'libtiledb=\d+\.\d+\.\d+', first):
                raise RuntimeError(f"Unrecognized first line of tiledbsoma_stats_dump(): {first}")
            stats = json.loads('\n'.join(lines))
        if reset:
            stats_reset()
    return stats


Fmt = Literal['png', 'md', 'fig']
SaveFmt = Literal['png', 'json']
Opt = Optional


@dataclass
class PlotConfigs:
    fmt: Fmt = 'fig'  # return the plot in this format
    w: int = 1200
    h: int = 800
    save: list[SaveFmt] = field(default_factory=list)  # fmts to save plot as
    v: bool = True           # "verbose": log files written, fmt returned
    i: Opt[bool] = None      # "interactive": fallback to
    dir: Opt[str] = None     # output directory
    grid: Opt[str] = '#ccc'  # grid/axis colors
    bg: Opt[str] = 'white'   # background color

    @property
    def interactive(self):
        return self.fmt == 'fig'


# Global object, overwrite members to control default behavior
plot_configs = PlotConfigs()
pc = plot_configs


def plot(
    fig: Figure,
    name: str,
    **kwargs,
):
    global plot_configs
    defaults = {
        k: v
        for k, v in asdict(plot_configs).items()
        if k not in kwargs
    }
    c = PlotConfigs(**dict(**defaults, **kwargs))

    def log(msg):
        """Maybe log ``msg`` to ``stderr``."""
        if c.v:
            err(msg)

    def mkpath(fmt: SaveFmt):
        path = f'{name}.{fmt}'
        if c.dir:
            path = join(c.dir, path)
        log(f'Saving: {path}')
        return path

    # Set plot defaults / expand `PlotConfigs` properties
    fig.update_layout(title=dict(x=0.5))
    if c.bg:
        fig.update_layout(plot_bgcolor=c.bg)
    grid = c.grid
    if c.grid:
        fig.update_xaxes(
            gridcolor=grid,
            zerolinecolor=grid,
            zerolinewidth=1,
        ).update_yaxes(
            gridcolor=grid,
            zerolinecolor=grid,
            zerolinewidth=1,
        )

    # Save plot as png and/or JSON
    img_kwargs = dict(width=c.w, height=c.h)
    if 'png' in c.save:
        path = mkpath('png')
        fig.write_image(path, **img_kwargs)
    if 'json' in c.save:
        path = mkpath('json')
        fig.write_json(path)

    # Return plot as Plotly, Markdown, or Image
    # - Plotly is nice in interactive notebooks, but is bad for committing to Git (>3MB of HTML/JS/CSS)
    # - Markdown is nice for committing to Git (it's just `![](path-to-img.png)`), but Github / nbviewer don't render
    #   it properly.
    # - Image is a compromise, can bloat `.ipynb`, but renders in most web viewers.
    fmt = c.fmt
    if fmt == 'fig':
        log("Returning Plotly Figure")
        return fig
    elif fmt == 'md':
        if not 'png' in c.save:
            raise ValueError(f"Can't return markdown as `png` wasn't included in `save`")
        log("Returning IPython Markdown")
        return Markdown(f'![]({mkpath("png")})')
    elif fmt == 'png':
        log("Returning IPython Image")
        return Image(fig.to_image(**img_kwargs))
    else:
        raise ValueError(f"Unrecognized fmt: {fmt}")