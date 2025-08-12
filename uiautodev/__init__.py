#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Mar 04 2024 14:28:53 by codeskyblue
"""

# version is auto managed by poetry
__version__ = "0.9.1"

import sys
import subprocess
import whichcraft
from pathlib import Path

_BIN_DIR = Path(__file__).with_suffix('').parent / "binaries"


def _run(cmd, **kw):
    """静默执行，失败抛异常。"""
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)


def _find_uv():
    """返回 ['uv','pip'] 或 None"""
    uv = whichcraft.which("uv") or whichcraft.which("uv.exe")
    return [uv, "pip"] if uv else None


def _find_pip():
    """返回 ['python','-m','pip'] 或 None"""
    try:
        _run([sys.executable, "-m", "pip", "--version"])
        return [sys.executable, "-m", "pip"]
    except Exception:
        return None


def _ensure_pip():
    """没有 pip 就现场装。"""
    try:
        _run([sys.executable, "-m", "pip", "--version"])
        return
    except Exception:
        pass

    try:
        import ensurepip  # noqa
        _run([sys.executable, "-m", "ensurepip", "--upgrade"])
    except Exception:
        # 最后兜底：get-pip.py
        import urllib.request
        url = "https://bootstrap.pypa.io/get-pip.py"
        with urllib.request.urlopen(url) as resp:
            code = resp.read()
        _run([sys.executable, "-c", code])


def _install_local_deps():
    """安装 binaries/ 下所有 tar.gz"""
    tars = list(_BIN_DIR.glob("*.tar.gz"))
    if not tars:
        return

    cmd = _find_uv() or _find_pip()
    if cmd is None:
        _ensure_pip()
        cmd = [sys.executable, "-m", "pip"]

    for tb in tars:
        try:
            import uiautomator2  # 已装就跳过
            break
        except ModuleNotFoundError:
            _run(cmd + ["install", str(tb)])


# 首包导入时自动执行
_install_local_deps()
