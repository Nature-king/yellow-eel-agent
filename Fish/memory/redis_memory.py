import json

import redis

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    HumanMessage,
    AIMessage
)


class RedisMessageHistory(BaseChatMessageHistory):

    def __init__(
        self,
        session_id,
        url="redis://127.0.0.1:6379"
    ):

        self.session_id = session_id

        self.redis_client = redis.Redis.from_url(
            url,
            decode_responses=True,
            protocol=2
        )


        self.key = (
            f"chat_history:{session_id}"
        )

    @property
    def messages(self):

        # 最近3轮对话 = 6条消息
        max_messages = 6

        data = self.redis_client.lrange(
            self.key,
            -max_messages,
            -1
        )

        messages = []

        for item in data:

            msg = json.loads(item)

            if msg["type"] == "human":

                messages.append(
                    HumanMessage(
                        content=msg["content"]
                    )
                )

            elif msg["type"] == "ai":

                messages.append(
                    AIMessage(
                        content=msg["content"]
                    )
                )

        print(
            f"[Redis记忆] 会话: {self.session_id} | "
            f"传入历史消息: {len(messages)}条"
        )

        return messages



    def add_message(self,message):

        if isinstance(
            message,
            HumanMessage
        ):

            data={
                "type":"human",
                "content":message.content
            }


        elif isinstance(
            message,
            AIMessage
        ):

            data={
                "type":"ai",
                "content":message.content
            }

        else:
            return


        self.redis_client.rpush(
            self.key,
            json.dumps(
                data,
                ensure_ascii=False
            )
        )



    def clear(self):

        self.redis_client.delete(
            self.key
        )