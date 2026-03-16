"""主程序。

会自动加载plugins目录下的所有模块。
"""

import argparse
import asyncio
import importlib
import os
import pkgutil
import sys
import traceback

import uvicorn
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from . import Bot, Dispatcher, Plugin
from . import plugins as plugins_module

parser = argparse.ArgumentParser()
parser.add_argument("--cwd", type=str, default=".", help="保存运行数据的工作目录")
args = parser.parse_args()
os.makedirs(args.cwd, exist_ok=True)
os.chdir(args.cwd)
print("工作目录 =", os.getcwd())

bot = Bot()

for p in sorted(m.name for m in pkgutil.iter_modules(plugins_module.__path__)):
    print(f"加载插件模块 {p}")
    try:
        importlib.import_module(f"{plugins_module.__name__}.{p}")
    except Exception:
        print("导入插件模块时发生错误，继续……")
        traceback.print_exc()


# 虽然只是加载而没有将模块留下，但是其中的类皆已成功定义。
# 靠深度优先搜索找出所有继承了Plugin但没有子类的类，它们是要实例化的插件类。
def leaf_subclasses(cls: type) -> list[type]:
    """找出指定类的所有叶子类。"""
    return [s for c in cls.__subclasses__() for s in leaf_subclasses(c)] or [cls]


plugins: list[Plugin] = []
for p in leaf_subclasses(Plugin):
    print(f"加载插件类 {p.__name__}")
    try:
        p = p()
        p.bot = bot
        plugins.append(p)
    except Exception:
        print("实例化插件类时发生错误，继续……")
        traceback.print_exc()

# 上述过程中易碎的细节：
# • 插件模块相互独立，从而按导入顺序加载。
# • Python 3.4起，__subclasses__按字典键的顺序返回子类列表。
# • Python 3.6起，字典按加入顺序迭代键。
# • Python 3.9起，文档明确指出__subclasses__按子类定义先后顺序返回子类列表。
# • leaf_subclasses函数返回列表从而保持顺序。

dispatcher = Dispatcher(bot, plugins)


class Root(HTTPEndpoint):
    async def get(self, request: Request) -> Response:
        return JSONResponse(
            {
                "消息处理端": "已启动",
                "pid": os.getpid(),
                "argv": sys.argv,
                "request_headers": dict(request.headers),
            }
        )

    async def post(self, request: Request) -> Response:
        # 近来，异步Python大受追捧，旧框架加入异步用法，新框架更是只支持异步。
        # 异步带来的好处只在非常特定的场合适用，带来的代码复杂度却是所有选择支持异步的项目都无法避免的。
        # 作为后来居上的语言功能，Python中的异步复杂度远远高于JavaScript这样原本就只有异步的语言。
        # 随着GIL限制解除，线程的优势愈发显著，我甚至相信异步Python将来会被废弃。
        # 为了用上更现代的新框架的同时维持业务代码的编写体验不变，我选择把异步病毒隔离。
        await asyncio.to_thread(dispatcher.on_event, await request.json())
        return PlainTextResponse("")


uvicorn.Server(
    uvicorn.Config(
        Starlette(
            routes=[
                Route("/", Root),
            ]
        ),
        port=5701,
        log_level="info",
    )
).run()
