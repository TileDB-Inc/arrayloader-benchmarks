import gc
from dataclasses import dataclass
from time import time
from typing import Optional

from cellxgene_census.experimental.ml import ExperimentDataPipe
from torch.utils.data import DataLoader
from tqdm import tqdm


@dataclass
class Exp:
    datapipe: ExperimentDataPipe
    loader: DataLoader


@dataclass
class Batch:
    elapsed: float
    n_rows: int
    n_cols: int
    gc: Optional[float] = None


@dataclass
class Epoch:
    n_rows: int
    n_cols: int
    elapsed: float
    gc: float
    batches: list[Batch]


@dataclass
class Method:
    name: str
    epochs: list[Epoch]


@dataclass
class Results:
    census: Method
    merlin: Optional[Method] = None
    mapped_collection: Optional[Method] = None


def benchmark(
        exp: Exp,
        batch_size: int = 1024,
        gc_freq: int | None = None,
        exclude_first_batch: bool = True,
        progress_bar: bool = True,
        ensure_cuda: bool = True,
        max_batches: int | None = None,
) -> Epoch:
    n_samples, n_vars = exp.datapipe.shape
    loader_iter = exp.loader.__iter__()
    if exclude_first_batch:
        # Optionally exclude first batch from benchmark, as it may include setup time
        next(loader_iter)

    num_iter = (n_samples + batch_size - 1) // batch_size if n_samples is not None else None

    batches = []
    n_batches = num_iter if num_iter is not None else len(loader_iter)
    if max_batches and n_batches > max_batches:
        n_batches = max_batches
    batch_iter = enumerate(loader_iter)
    if progress_bar:
        batch_iter = tqdm(batch_iter, total=n_batches)

    start_time = batch_time = time()

    for i, batch in batch_iter:
        X = batch["x"] if isinstance(batch, dict) else batch[0]
        # for pytorch DataLoader
        # Merlin sends to cuda by default
        if ensure_cuda and hasattr(X, "is_cuda") and not X.is_cuda:
            X = X.cuda()

        if num_iter is not None and i == num_iter:
            break
        if max_batches and i == max_batches:
            break

        batch_elapsed = time() - batch_time

        gc_time = None
        if gc_freq and i % gc_freq == 0:
            gc_before = time()
            gc.collect()
            gc_time = time() - gc_before

        n_rows, n_cols = X.shape
        batches.append(Batch(elapsed=batch_elapsed, n_rows=n_rows, n_cols=n_cols, gc=gc_time))
        batch_time = time()

    execution_time = time() - start_time
    gc.collect()

    total_rows = sum(batch.n_rows for batch in batches)
    time_per_sample = 1e6 * execution_time / total_rows
    print(f'time per sample: {time_per_sample:.2f} μs')
    total_gc = sum(batch.gc or 0 for batch in batches)
    samples_per_sec = total_rows / execution_time
    print(f'samples per sec: {samples_per_sec:.2f} samples/sec')

    return Epoch(
        n_rows=total_rows,
        n_cols=n_vars,
        batches=batches,
        elapsed=execution_time,
        gc=total_gc,
    )
