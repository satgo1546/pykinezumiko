from typing import Any
import pykinezumiko


class BackstageOnly(pykinezumiko.Plugin):
    """拦截事件，只允许来自管理用群和无来源的事件抵达下面的插件。"""

    def on_event(self, data: dict[str, Any]) -> bool:
        return self.context_sender_from_gocqhttp_event(data)[0] not in (
            0,
            pykinezumiko.conf.BACKSTAGE,
        )
