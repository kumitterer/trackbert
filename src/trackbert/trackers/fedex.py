from .base import BaseTracker
from ..classes.database import Event

from fedextrack import FedEx as FedExAPI
from dateutil.parser import parse

import json
import logging


class FedEx(BaseTracker):
    def __init__(self, *args, **kwargs):
        self.api = FedExAPI.from_config("config.ini")

    def get_status(self, tracking_number, carrier):
        response = self.api.track_by_tracking_number(tracking_number)

        try:
            all_results = response["output"]["completeTrackResults"][0]["trackResults"]
            
            all_events = []

            for result in all_results:
                events = result["scanEvents"]
                for event in events:
                    all_events.append(event)

            logging.debug(f"Got events for {tracking_number}: {len(all_events)}")
        except KeyError:
            logging.error(f"Error getting events for {tracking_number}: {all_events}")
            return

        events = sorted(
            all_events, key=lambda x: x["date"], reverse=True
        )

        for event in events:
            event_time = parse(event["date"]).strftime("%Y-%m-%d %H:%M:%S")
            event_description = f"{event['scanLocation']['city'], event['scanLocation']['countryCode']} {event['eventDescription']}"

            yield Event(
                shipment_id=0,
                event_time=event_time,
                event_description=event_description,
                raw_event=json.dumps(event),
            )

    def supported_carriers(self):
        return [
            ("fedex", 100),
        ]


tracker = FedEx
