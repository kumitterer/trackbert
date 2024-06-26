from ..classes.provider import BaseProvider
from ..classes.database import Event

from pykeydelivery import KeyDelivery as KeyDeliveryAPI

import json
import logging


class KeyDelivery(BaseProvider):
    def __init__(self, *args, **kwargs):
        self.api = KeyDeliveryAPI.from_config(str(kwargs.get("config")))

    def get_status(self, tracking_number, carrier):
        all_events = self.api.realtime(carrier, tracking_number)

        try:
            logging.debug(
                f"Got events for {tracking_number}: {len(all_events['data']['items'])}"
            )
        except KeyError:
            logging.error(f"Error getting events for {tracking_number}: {all_events}")
            return

        events = sorted(
            all_events["data"]["items"], key=lambda x: x["time"], reverse=True
        )

        for event in events:
            yield Event(
                shipment_id=0,
                event_time=event["time"],
                event_description=event["context"],
                raw_event=json.dumps(event),
            )

    def supported_carriers(self):
        try:
            response = self.api.list_carriers()
            carriers = [
                (carrier["code"], 1, carrier["name"]) for carrier in response["data"]
            ]
            return carriers
        except Exception:
            return [
                ("*", 1),
            ]


provider = KeyDelivery
