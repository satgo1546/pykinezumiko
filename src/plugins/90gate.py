from typing import Any
from .. import ChatbotBehavior, conf


class InteriorOnly(ChatbotBehavior):
    """拦截事件，只允许来自的管理用群和无来源事件抵达下面的插件。"""

    def gocqhttp_event(self, data: dict[str, Any]) -> bool:
        return self.context_sender_from_gocqhttp_event(data)[0] not in (
            0,
            conf.INTERIOR,
        )
