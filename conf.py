# 存储到处都要使用的全局配置。

INTERIOR = -114514
"""管理用群。调试信息将发送到此处；管理用插件也只接受来自其中的管理命令。"""

# 下列选项用于Sphinx文档生成器。
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "pykinezumiko"
copyright = "2023 木鼠子制作群"
author = "Frog Chen & Akhia"

extensions = ["sphinx.ext.autodoc"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "zh_CN"

html_theme = "alabaster"
html_static_path = ["_static"]
