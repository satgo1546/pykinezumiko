from typing import Any
import pykinezumiko


class BackstageOnly(pykinezumiko.Plugin):
    """拦截事件，只允许来自管理用群和无来源的事件抵达下面的插件。"""

    def on_event(self, context: int, sender: int, data: dict[str, Any]) -> bool:
        return context not in (0, pykinezumiko.conf.BACKSTAGE)
