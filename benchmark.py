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
    batch: float
    gc: Optional[float] = None


@dataclass
class Epoch:
    time_per_sample: float
    samples_per_sec: float
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


def benchmark(exp: Exp, batch_size: int = 1024, gc_freq: Optional[int] = None) -> Epoch:
    n_samples = exp.datapipe.shape[0]
    loader_iter = exp.loader.__iter__()
    # exclude first batch from benchmark as this includes the setup time
    batch = next(loader_iter)

    num_iter = n_samples // batch_size if n_samples is not None else None

    batches = []
    start_time = batch_time = time()

    total = num_iter if num_iter is not None else len(loader_iter)
    for i, batch in tqdm(enumerate(loader_iter), total=total):
        X = batch["x"] if isinstance(batch, dict) else batch[0]
        # for pytorch DataLoader
        # Merlin sends to cuda by default
        if hasattr(X, "is_cuda") and not X.is_cuda:
            X = X.cuda()

        if num_iter is not None and i == num_iter:
            break

        batch_elapsed = time() - batch_time

        gc_time = None
        if gc_freq and i % gc_freq == 0:
            gc_before = time()
            gc.collect()
            gc_time = time() - gc_before

        batches.append(Batch(batch_elapsed, gc_time))
        batch_time = time()

    execution_time = time() - start_time
    gc.collect()

    time_per_sample = (1e6 * execution_time) / (total * batch_size)
    print(f'time per sample: {time_per_sample:.2f} μs')
    samples_per_sec = total * batch_size / execution_time
    print(f'samples per sec: {samples_per_sec:.2f} samples/sec')

    return Epoch(samples_per_sec=samples_per_sec, time_per_sample=time_per_sample, batches=batches)