"""图像文档存储：document_id → 内存 ndarray（协议 §4：Worker 持有文档状态）。"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from processors.utils import load_image, save_image


class WorkerError(Exception):
    """带稳定错误码的业务异常，dispatcher 据此构造协议错误响应。"""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class Document:
    document_id: str
    source: str
    image: np.ndarray
    format: str = ''
    modified: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


class DocumentStore:
    """线程安全的文档表。Worker 进程内单实例。"""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._lock = threading.Lock()

    def open(self, path: str) -> Document:
        src = Path(path)
        if not src.is_file():
            raise WorkerError('FILE_NOT_FOUND', f'文件不存在: {path}')
        try:
            image = load_image(src)
        except FileNotFoundError as exc:
            raise WorkerError('FILE_NOT_FOUND', f'文件不存在: {path}') from exc
        except Exception as exc:  # PIL/cv2 解码失败的形态过多，统一归一
            raise WorkerError('UNSUPPORTED_FORMAT', f'无法解码图像: {exc}') from exc
        if image is None or getattr(image, 'size', 0) == 0:
            raise WorkerError('UNSUPPORTED_FORMAT', f'解码结果为空: {path}')

        doc = Document(
            document_id=f'doc-{uuid.uuid4().hex[:8]}',
            source=str(src.resolve()),
            image=image,
            format=src.suffix.lower().lstrip('.'),
        )
        with self._lock:
            self._docs[doc.document_id] = doc
        return doc

    def get(self, document_id: str) -> Document:
        with self._lock:
            doc = self._docs.get(document_id)
        if doc is None:
            raise WorkerError('UNKNOWN_DOCUMENT', f'文档不存在或已关闭: {document_id}')
        return doc

    def close(self, document_id: str) -> bool:
        with self._lock:
            return self._docs.pop(document_id, None) is not None

    def close_all(self) -> None:
        with self._lock:
            self._docs.clear()

    def save(self, document_id: str, path: str, quality: int | None = None) -> dict[str, Any]:
        doc = self.get(document_id)
        target = Path(path)
        try:
            kwargs = {'quality': quality} if quality is not None else {}
            saved = save_image(doc.image, target, **kwargs)
        except Exception as exc:
            raise WorkerError('ENGINE_ERROR', f'保存失败: {exc}') from exc
        return {'saved': True, 'path': str(saved), 'file_size': saved.stat().st_size}
