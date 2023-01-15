"""存储到处都要使用的全局配置。"""
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

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
