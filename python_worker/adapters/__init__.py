"""Worker 适配层：把协议动作翻译到现有 processors/backends 资产上。

适配层是唯一允许 import processors 的地方（dispatcher/runtime 保持引擎无关），
保证迁移期"先建适配层，再迁移功能"的规则（总纲 §15.5）。
"""
