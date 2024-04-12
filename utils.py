from dataclasses import dataclass, asdict, field
import gc
import json
from math import log10
import os
from os.path import exists, join, splitext
from shutil import rmtree
from sys import stderr
import time
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