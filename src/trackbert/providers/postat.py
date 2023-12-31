from ..classes.provider import BaseProvider
from ..classes.database import Event

import json
import logging

from dateutil.parser import parse
from postat.classes.api import PostAPI


class PostAT(BaseProvider):
    def __init__(self, *args, **kwargs):
        pass

    def get_status(self, tracking_number, carrier):
        api = PostAPI()

        try:
            status = api.get_shipment_status(tracking_number)
            shipment = status["data"]["einzelsendung"]
            events = shipment["sendungsEvents"]

            for event in events:
                timestamp = event["timestamp"]
                py_timestamp = parse(timestamp)
                event_time = py_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                yield Event(
                    shipment_id=0,
                    event_time=event_time,
                    event_description=event["text"],
                    raw_event=json.dumps(event),
                )

        except Exception as e:
            logging.error(f"Error while fetching status: {e}")

    def supported_carriers(self):
        return [
            ("austrian_post", 100, "Austrian Post"),
        ]


provider = PostAT
