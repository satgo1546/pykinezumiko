from .. import ChatbotBehavior, docstore


class 一条数据(docstore.Record):
    text: str


class CRUD(ChatbotBehavior):
    def on_command_crud_insert(self, k: str, v: str):
        一条数据[k] = 一条数据(text=v)
        return k

    def on_command_crud_select(self):
        return "\n".join(f"{k}: {v.text}" for k, v in 一条数据.items()) if len(一条数据) else "空"

    on_command_crud_update = on_command_crud_insert

    def on_command_crud_delete(self, k: str):
        del 一条数据[k]
        return k
