#!/usr/bin/env python3
"""存储到处都要使用的全局配置；运行本脚本调用Sphinx生成文档页。"""
import os
import sys

INTERIOR = -114514
"""管理用群。调试信息将发送到此处；管理用插件也只接受来自其中的管理命令。"""

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

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

if __name__ == "__main__":
    os.chdir(project_root)
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
            "src",
        ],
        check=True,
    )
    shutil.copyfile("index.rst", "_docs/index.rst")
    subprocess.run(
        ["sphinx-build", "-a", "-b", "html", "-c", "src", "_docs", "_site"], check=True
    )
