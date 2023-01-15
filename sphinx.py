#!/usr/bin/env python3
import os
import subprocess
import shutil

os.chdir(os.path.dirname(__file__))

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
