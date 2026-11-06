"""JSON Lines 协议编解码与消息构造（docs/ipc-protocol.md §2/§5/§8）。"""
from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = 1

# 稳定错误码（docs/ipc-protocol.md §5）。
ERR_PARSE = 'PARSE_ERROR'
ERR_PROTOCOL_MISMATCH = 'PROTOCOL_MISMATCH'
ERR_UNKNOWN_ACTION = 'UNKNOWN_ACTION'
ERR_INVALID_PARAMS = 'INVALID_PARAMS'
ERR_UNKNOWN_DOCUMENT = 'UNKNOWN_DOCUMENT'
ERR_UNKNOWN_TASK = 'UNKNOWN_TASK'
ERR_FILE_NOT_FOUND = 'FILE_NOT_FOUND'
ERR_UNSUPPORTED_FORMAT = 'UNSUPPORTED_FORMAT'
ERR_UNREDOABLE = 'UNREDOABLE'  # docs/ipc-protocol.md §5：undo/redo 栈空（提交前同步返回）
ERR_CANCELLED = 'CANCELLED'
ERR_ENGINE_ERROR = 'ENGINE_ERROR'
ERR_INTERNAL = 'INTERNAL'


class ProtocolError(Exception):
    """协议层错误（编解码、字段校验失败）。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def encode(msg: dict[str, Any]) -> str:
    """编码一行协议消息（含换行符）。stdout 只允许输出该函数的结果。"""
    return json.dumps(msg, ensure_ascii=False, separators=(',', ':')) + '\n'


def decode(line: str) -> dict[str, Any]:
    try:
        msg = json.loads(line)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProtocolError(ERR_PARSE, f'消息不是合法 JSON: {exc}') from exc
    if not isinstance(msg, dict):
        raise ProtocolError(ERR_PARSE, '消息必须是 JSON 对象')
    validate_request(msg)
    return msg


def validate_request(msg: dict[str, Any]) -> None:
    """校验请求必需字段与协议版本；事件/响应（含 type 字段）跳过版本校验。"""
    if 'type' in msg:
        return
    protocol = msg.get('protocol')
    if not isinstance(protocol, int):
        raise ProtocolError(ERR_PARSE, '缺少 protocol 字段')
    if protocol != PROTOCOL_VERSION:
        raise ProtocolError(
            ERR_PROTOCOL_MISMATCH,
            f'协议版本不受支持: 请求 {protocol}, Worker {PROTOCOL_VERSION}',
        )
    if not msg.get('request_id'):
        raise ProtocolError(ERR_PARSE, '缺少 request_id')
    if not msg.get('action'):
        raise ProtocolError(ERR_PARSE, '缺少 action')


def make_response(request_id: str, success: bool, result: dict | None = None,
                  error: dict | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {'protocol': PROTOCOL_VERSION, 'request_id': request_id, 'success': success}
    if success:
        msg['result'] = result or {}
    else:
        msg['error'] = error or {'code': ERR_INTERNAL, 'message': '未知错误', 'details': {}}
    return msg


def make_error(request_id: str, code: str, message: str,
               details: dict | None = None) -> dict[str, Any]:
    return make_response(request_id, False, error={
        'code': code, 'message': message, 'details': details or {},
    })


def make_progress(task_id: str, progress: int, message: str = '',
                  extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """task.progress 事件（§2.3）。extra 为动作特有增补字段（如批处理的
    done/total/current/state，docs/ipc-protocol.md §3.5）；消费方必须忽略
    未知字段，故纯新增、既有动作不传 extra 时消息形状逐字节不变。"""
    msg: dict[str, Any] = {
        'protocol': PROTOCOL_VERSION,
        'type': 'task.progress',
        'task_id': task_id,
        'progress': max(0, min(100, int(progress))),
        'message': message,
    }
    if extra:
        msg.update(extra)
    return msg


def make_task_completed(task_id: str, result: dict | None = None) -> dict[str, Any]:
    return {
        'protocol': PROTOCOL_VERSION,
        'type': 'task.completed',
        'task_id': task_id,
        'result': result or {},
    }


def make_task_failed(task_id: str, code: str, message: str,
                     details: dict | None = None) -> dict[str, Any]:
    return {
        'protocol': PROTOCOL_VERSION,
        'type': 'task.failed',
        'task_id': task_id,
        'error': {'code': code, 'message': message, 'details': details or {}},
    }


def make_log(level: str, message: str) -> dict[str, Any]:
    return {'protocol': PROTOCOL_VERSION, 'type': 'log', 'level': level, 'message': message}
