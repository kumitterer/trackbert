from .base import BaseTracker
from ..classes.database import Event

from dhltrack import DHL as DHLAPI
from dateutil.parser import parse

import json
import logging


class DHL(BaseTracker):
    def __init__(self, *args, **kwargs):
        self.api = DHLAPI.from_config("config.ini")

    def get_status(self, tracking_number, carrier):
        response = self.api.track(tracking_number)

        try:
            all_events = response["shipments"][0]["events"]
            logging.debug(f"Got events for {tracking_number}: {len(all_events)}")

        except KeyError:
            logging.error(f"Error getting events for {tracking_number}: {all_events}")
            return

        events = sorted(
            all_events, key=lambda x: x["timestamp"], reverse=True
        )

        for event in events:
            event_time = parse(event["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            
            try:
                event_locality = f"[{event['location']['address']['addressLocality']}] "
            except KeyError:
                event_locality = ""

            event_description = f"{event_locality}{event['description']}"

            yield Event(
                shipment_id=0,
                event_time=event_time,
                event_description=event_description,
                raw_event=json.dumps(event),
            )

    def supported_carriers(self):
        return [
            ("dhl", 100),
        ]


tracker = DHL
