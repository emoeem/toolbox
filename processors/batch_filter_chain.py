from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from .cancellation import CancelToken, CancelledError
from .filter_chain import FilterChain, FilterStepError
from .utils import ensure_rgb, load_image, save_image


class BatchItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchItemResult:
    source: Path
    output: Path | None = None
    status: BatchItemStatus = BatchItemStatus.PENDING
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class BatchFilterChainResult:
    items: list[BatchItemResult] = field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    total: int = 0


def run_batch_filter_chain(
    files: list[Path | str],
    chain: FilterChain,
    output_dir: Path | str | None = None,
    output_format: str = "PNG",
    progress_cb=None,
    cancel_token: CancelToken | None = None,
    overwrite: bool = True,
) -> BatchFilterChainResult:
    from time import monotonic
    result = BatchFilterChainResult()
    paths = [Path(f) for f in files]
    result.total = len(paths)
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
    else:
        out = None
    for idx, src in enumerate(paths):
        result.items.append(BatchItemResult(source=src))
    for i, src in enumerate(paths):
        if cancel_token is not None:
            if cancel_token.is_cancelled():
                for j in range(i, len(paths)):
                    if result.items[j].status == BatchItemStatus.PENDING:
                        result.items[j].status = BatchItemStatus.CANCELLED
                        result.cancelled += 1
                break
        item = result.items[i]
        item.status = BatchItemStatus.RUNNING
        t0 = monotonic()
        try:
            img = load_image(str(src))
            img = ensure_rgb(img)
            processed = chain.apply(img, cancel_token=cancel_token)
            if out is not None:
                out_name = src.stem + "." + output_format.lower().replace("jpeg", "jpg")
                out_path = out / out_name
                if out_path.exists() and not overwrite:
                    item.status = BatchItemStatus.FAILED
                    item.error = f"输出已存在且 overwrite=False: {out_path}"
                    result.failed += 1
                else:
                    save_image(processed, str(out_path))
                    item.output = out_path
                    item.status = BatchItemStatus.SUCCEEDED
                    result.succeeded += 1
            else:
                item.status = BatchItemStatus.SUCCEEDED
                result.succeeded += 1
        except CancelledError:
            item.status = BatchItemStatus.CANCELLED
            item.error = "取消"
            result.cancelled += 1
            for j in range(i + 1, len(paths)):
                if result.items[j].status == BatchItemStatus.PENDING:
                    result.items[j].status = BatchItemStatus.CANCELLED
                    result.cancelled += 1
            break
        except FilterStepError as exc:
            item.status = BatchItemStatus.FAILED
            item.error = str(exc)
            result.failed += 1
        except Exception as exc:
            item.status = BatchItemStatus.FAILED
            item.error = str(exc)
            result.failed += 1
        finally:
            item.elapsed_ms = (monotonic() - t0) * 1000
            if progress_cb is not None:
                try:
                    progress_cb(i + 1, len(paths), item.status.value)
                except Exception:
                    pass
    return result
