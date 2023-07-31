"""存储到处都要使用的全局配置。"""
import pygments.style
import pygments.token

BACKSTAGE = -114514
"""管理用群。调试信息将发送到此处；管理用插件也只接受来自其中的管理命令。"""

THEME = ("#000000", "#b53d00", "#ffcc80", "#fff3e0")
"""文字色、深色前景、深色背景、浅色背景。"""
ACCENTS = ("#b71c1c", "#827717", "#33691e", "#009095", "#0d47a1", "#4a148c")
"""用于图表等的红黄绿青蓝紫。"""


class PygmentsStyle(pygments.style.Style):
    """代码高亮的样式。"""
    styles = {
        # 【编程语言】
        # 红：关键字。
        pygments.token.Keyword: ACCENTS[0],
        pygments.token.Name.Builtin.Pseudo: ACCENTS[0],
        pygments.token.Name.Function.Magic: ACCENTS[0],
        pygments.token.Name.Variable.Magic: ACCENTS[0],
        pygments.token.Operator.Word: ACCENTS[0],
        # 黄：字符串。
        pygments.token.String: ACCENTS[1],
        # 绿：注释。
        pygments.token.Comment: ACCENTS[2],
        pygments.token.String.Doc: ACCENTS[2],
        # 青：符号。
        pygments.token.Operator: ACCENTS[3],
        pygments.token.Punctuation: ACCENTS[3],
        pygments.token.String.Interpol: ACCENTS[3],
        # 蓝：数值。
        pygments.token.Literal: ACCENTS[4],
        pygments.token.String.Symbol: ACCENTS[4],
        # 紫：魔法。
        pygments.token.Comment.Preproc: ACCENTS[5],
        pygments.token.Comment.PreprocFile: ACCENTS[5],
        pygments.token.Name.Entity: ACCENTS[5],
        pygments.token.Name.Decorator: ACCENTS[5],
        # 主题色：系统。
        pygments.token.Generic.Prompt: THEME[1],
        pygments.token.Generic.Punctuation.Marker: THEME[1],
        # 【非程序】
        pygments.token.Generic.Inserted: ACCENTS[2],
        pygments.token.Generic.Deleted: ACCENTS[0],
        pygments.token.Generic.Subheading: "bold",
        pygments.token.Generic.Emph: "italic",
        pygments.token.Generic.EmphStrong: "bold",
    }
