import json
from abc import ABC
from contextlib import redirect_stdout, contextmanager
from json import JSONDecodeError
from os.path import join
from re import fullmatch
from tempfile import TemporaryDirectory

from tiledbsoma import (
    tiledbsoma_stats_enable,
    tiledbsoma_stats_disable,
    tiledbsoma_stats_reset,
    tiledbsoma_stats_dump,
)
import tiledb


class Stats(ABC):
    def __init__(self):
        self.stats = {}

    def enable(self) -> None:
        raise NotImplementedError

    def disable(self) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def dump(self) -> None:
        raise NotImplementedError

    def header_regexs(self) -> list[str]:
        raise NotImplementedError

    def get(self, reset: bool = False) -> dict:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = join(tmp_dir, 'stats.txt')
            with open(tmp_path, 'w') as f:
                with redirect_stdout(f):
                    self.dump()
            with open(tmp_path, 'r') as f:
                lines = [ line.rstrip('\n') for line in f.readlines() ]
                header_regexs = self.header_regexs()
                for idx, header_regex in enumerate(header_regexs):
                    line = lines[idx]
                    if not fullmatch(header_regex, line):
                        raise RuntimeError(f"Expected line {idx+1} to match {header_regex}: {line}")
                stats = json.loads('\n'.join(lines[len(header_regexs):]))
            if reset:
                self.reset()
        return stats

    @contextmanager
    def collect(self, name: str):
        stats = self.stats
        if 'name' in stats:
            raise ValueError(f'Name {name} already exists in stats obj')
        self.reset()
        self.enable()
        try:
            yield
        finally:
            self.disable()
            cur_stats = self.get()
            stats[name] = cur_stats


class TileDBSomaStats(Stats):
    def enable(self) -> None:
        tiledbsoma_stats_enable()

    def disable(self) -> None:
        tiledbsoma_stats_disable()

    def reset(self) -> None:
        tiledbsoma_stats_reset()

    def dump(self) -> None:
        tiledbsoma_stats_dump()

    def header_regexs(self) -> list[str]:
        return [r'libtiledb=\d+\.\d+\.\d+']


class TileDBStats(Stats):
    def enable(self) -> None:
        tiledb.stats_enable()

    def disable(self) -> None:
        tiledb.stats_disable()

    def reset(self) -> None:
        tiledb.stats_reset()

    def dump(self) -> None:
        tiledb.stats_dump()

    def header_regexs(self) -> list[str]:
        return [
            r'TileDB Embedded Version: \(\d+, \d+, \d+\)',
            r'TileDB-Py Version: \d+\.\d+\.\d+',
        ]
