from typing import Dict, Any
from urllib.request import Request, urlopen

import json

from ..classes.notifier import BaseNotifier


class Matrix(BaseNotifier):
    def __init__(self, **kwargs):
        self.config = kwargs["config"]

    def enabled(self) -> bool:
        return bool(self.config)

    def notify(self, title: str, message: str, urgent: bool = False) -> None:
        homeserver = self.config["homeserver"]
        room_id = self.config["room_id"]
        token = self.config["token"]

        url = f"{homeserver}/_matrix/client/r0/rooms/{room_id}/send/m.room.message?access_token={token}"

        data = json.dumps(
            {"msgtype": "m.text", "body": f"{title}\n\n{message}"}
        ).encode("utf-8")

        req = Request(url, data=data, headers={"Content-Type": "application/json"})

        urlopen(req)


notifier = Matrix
