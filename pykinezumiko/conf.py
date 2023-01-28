#!/usr/bin/env python3
"""存储到处都要使用的全局配置；运行本脚本调用pdoc生成文档页。"""
import sys

INTERIOR = -114514
"""管理用群。调试信息将发送到此处；管理用插件也只接受来自其中的管理命令。"""

THEME = ("#000000", "#b53d00", "#ffcc80", "#fff3e0")
"""文字色、深色前景、深色背景、浅色背景。"""
ACCENTS = ("#b71c1c", "#827717", "#33691e", "#006064", "#0d47a1", "#4a148c")
"""用于图表等的红黄绿青蓝紫。"""

if __name__ == "__main__":
    import subprocess

    subprocess.run(
        [
            "pdoc",
            "--template-directory",
            "docs/template",
            "pykinezumiko",
        ]
        + sys.argv[1:],
        check=True,
    )
