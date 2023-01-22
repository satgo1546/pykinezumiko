from .. import ChatbotBehavior, docstore


class 一条数据(docstore.Record):
    text: str


class CRUD(ChatbotBehavior):
    def on_command_insert(self, k: str, v: str):
        一条数据.table[k] = 一条数据(text=v)
        return k

    def on_command_select(self):
        return "\n".join(f"{k}: {v.text}" for k, v in 一条数据.table.items()) if len(一条数据.table) else "空"

    on_command_update = on_command_insert

    def on_command_delete(self, k: str):
        del 一条数据.table[k]
        return k
