import os
import sys
import subprocess
import urllib.request
import base64
from typing_extensions import Buffer
import zipfile
import tempfile
import urllib.parse
import mistletoe
import pygments
import pygments.lexers
import pygments.formatters
import pygments.style
import pygments.token

from . import conf


def font_face(
    woff2: Buffer, name: str, weight: str = "normal", style: str = "normal"
) -> str:
    """生成内联WOFF2字体数据的CSS字体声明。"""
    return f"""
@font-face {{
    font-family: "{name}";
    src: url(data:application/font-woff2;base64,{base64.b64encode(woff2).decode()}) format("woff2");
    font-weight: {weight};
    font-style: {style};
}}
"""


class HTMLFormatter(pygments.formatters.HtmlFormatter):
    def __init__(self) -> None:
        super().__init__(style=conf.PygmentsStyle)

    def get_linenos_style_defs(self) -> list[str]:
        return []


source_formatter = HTMLFormatter()


def make() -> None:
    # 缓存字体。
    os.makedirs("cache", exist_ok=True)
    for local, remote in {
        "cache/hei.otf": "https://mirrors.ctan.org/fonts/fandol/FandolHei-Regular.otf",
        "cache/jb.zip": "https://download.jetbrains.com/fonts/JetBrainsMono-2.304.zip",
    }.items():
        if not os.path.exists(local):
            urllib.request.urlretrieve(remote, local)
    # 打印HTML头部。
    # 样式表中不包含字体，因为需要在打印完整个文档后统计用到的字符，子集化中文字体。
    print(
        f"""<!DOCTYPE html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>pykinezumiko — 木鼠子 ⅱ Python Ver.</title>
<style>
body {{
    font: 14px/28px "JetBrains Mono", FandolHei, Courier, sans-serif;
    color: {conf.THEME[0]};
    background-color: {conf.THEME[2]};
    margin: 8px;
}}

main {{
    max-width: 66em;
    margin: 0 auto;
    border: 3px solid {conf.THEME[1]};
    padding: 4px 12px;
    background:
        0 27px url("data:image/svg+xml,{urllib.parse.quote(f'''
<svg xmlns='http://www.w3.org/2000/svg' width='8' height='28'>
<path d='m0 .5 h 4' stroke='{conf.THEME[2]}'/>
</svg>
''')}") content-box,
        {conf.THEME[3]};
    overflow: hidden;
}}

h1 {{
    margin: 14px -12px;
    padding: 0 12px;
    font-size: 28px;
    font-weight: inherit;
    line-height: 56px;
    color: {conf.THEME[1]};
    background-color: {conf.THEME[2]};
}}

h2, h3 {{
    margin: 0;
    font-size: inherit;
    font-weight: inherit;
    color: {conf.THEME[1]};
}}

h2 {{
    font-size: 16px;
}}

p {{
    margin: 0;
    text-indent: 2em;
}}

summary {{
    color: {conf.THEME[1]};
}}

pre, code {{
    margin: 0;
    font: inherit;
    white-space: pre-wrap;
}}

{source_formatter.get_style_defs()}
</style>
"""
    )
    characters = set()
    print("<main>")
    with open("README.md") as f:
        print(mistletoe.markdown(f))
    print("<h1>原理</h1>")
    print(end="<pre>")
    for filename in sorted(
        os.path.join(root, filename)
        for root, dirs, files in os.walk("pykinezumiko")
        for filename in files
        if filename.endswith(".py")
    ):
        characters.update(filename)
        print(end=f"<details><summary>{filename}</summary>")
        with open(filename, "r") as f:
            source = f.read()
            characters.update(source)
            pygments.highlight(
                source.rstrip(),
                pygments.lexers.get_lexer_for_filename(filename),
                source_formatter,
                sys.stdout,
            )
        print(end="</details>")
    print("</pre>")
    print("</main>")
    # 从中文字体中去除Latin-1字符集。
    characters.difference_update(chr(i) for i in range(256))
    # 打印字体声明。
    # 将字体内联在网页尾部的好处：
    # • 保持网页为单文件，轻松离线保存。
    # • 先加载更重要的网页内容，随后再加载字体。
    # • 尚未加载到@font-face声明时，浏览器认为指定的字体是本地字体。
    #   没有声明font-display: swap却有着一样的效果。
    print("<style>")
    with zipfile.ZipFile("cache/jb.zip") as z:
        with z.open("fonts/webfonts/JetBrainsMono-Regular.woff2") as f:
            print(font_face(f.read(), "JetBrains Mono"))
        with z.open("fonts/webfonts/JetBrainsMono-Bold.woff2") as f:
            print(font_face(f.read(), "JetBrains Mono", "bold"))
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "text"), "w") as f:
            f.write("".join(characters))
        subprocess.run(
            [
                "pyftsubset",
                "cache/hei.otf",
                f"--output-file={tmpdir}/subset",
                f"--text-file={tmpdir}/text",
                "--flavor=woff2",
                "--desubroutinize",
                "--obfuscate-names",
            ],
            check=True,
        )
        with open(os.path.join(tmpdir, "subset"), "rb") as f:
            print(font_face(f.read(), "FandolHei"))
    print("</style>")


if __name__ == "__main__":
    make()
