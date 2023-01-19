#!/usr/bin/env python3
"""存储到处都要使用的全局配置；运行本脚本调用Sphinx生成文档页。"""
import os
import sys

INTERIOR = -114514
"""管理用群。调试信息将发送到此处；管理用插件也只接受来自其中的管理命令。"""

THEME = ("#000000", "#b53d00", "#ffcc80", "#fff3e0")
"""文字色、深色前景、深色背景、浅色背景。"""
ACCENTS = ("#b71c1c", "#827717", "#33691e", "#006064", "#0d47a1", "#4a148c")
"""用于图表等的红黄绿青蓝紫。"""

# 下列选项用于Sphinx文档生成器。
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "pykinezumiko"
copyright = "2023 木鼠子制作群"
author = "Frog Chen & Akhia"

extensions = ["sphinx.ext.autodoc"]

templates_path = ["../docs/templates"]

language = "zh_CN"

html_theme = "basic"
html_static_path = ["../docs/resources"]
html_css_files = ["custom.css"]

sys.path.append(os.getcwd())

if __name__ == "__main__":
    import subprocess
    import shutil

    subprocess.run(
        [
            "sphinx-apidoc",
            "--force",
            "--implicit-namespaces",
            "--module-first",
            "-o",
            "_docs",
            "pykinezumiko",
        ],
        check=True,
    )
    shutil.copyfile("index.rst", "_docs/index.rst")
    subprocess.run(
        [
            "sphinx-build",
            "-a",
            "-b",
            "html",
            "-c",
            "pykinezumiko",
            "_docs",
            "_site",
        ],
        check=True,
    )
