"""
编码修复工具。

某些客户端（如 Windows 上 Tauri WebView2）在 multipart 请求中可能以系统
ANSI 编码（GBK 等）发送非 ASCII 文件名。starlette 用 UTF-8 解码失败后会
回退到 latin-1，导致中文文件名变成乱码。本模块提供恢复函数。
"""

from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_CANDIDATE_ENCODINGS = ("utf-8", "gbk", "big5", "shift_jis")


def recover_filename(name: str) -> str:
    """
    恢复被按 latin-1 误解码的文件名。

    当 `name` 是"原始字节按 latin-1 解码"的结果（即每个字符可编码回
    latin-1）时，尝试用常见编码重新解码；只有解码结果包含 CJK 字符且与
    原文不同才采用，否则保持原样。
    """
    try:
        raw = name.encode("latin-1")
    except UnicodeEncodeError:
        return name
    for encoding in _CANDIDATE_ENCODINGS:
        try:
            decoded = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        if decoded != name and _CJK_RE.search(decoded):
            return decoded
    return name
