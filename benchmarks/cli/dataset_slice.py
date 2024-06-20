import re
from dataclasses import dataclass


@dataclass
class DatasetSlice:
    start: int
    end: int
    sorted_datasets: bool

    def __repr__(self):
        s = 's' if self.sorted_datasets else ''
        if self.start:
            s += f'{self.start}'
        s += f':{self.end}'
        return s

    RGX = re.compile(r'(?P<sorted_datasets>s?)(?P<start>\d*):(?P<end>\d*)')

    @classmethod
    def parse(cls, s: str):
        m = cls.RGX.fullmatch(s)
        if not m:
            raise ValueError(f"Unrecognized DatasetSlice: {s}")
        start = m['start']
        return DatasetSlice(
            start=int(start) if start else 0,
            end=int(m['end']),
            sorted_datasets=bool(m['sorted_datasets']),
        )
