from .base import BaseTracker
from ..classes.database import Event

import json

from dateutil.parser import parse
from glsapi.classes.api import GLSAPI


class GLS(BaseTracker):
    def __init__(self, *args, **kwargs):
        pass

    def get_status(self, tracking_number, carrier):
        api = GLSAPI()
        status = api.tracking(tracking_number)
        events = status["tuStatus"][0]["history"]

        for event in events:
            event_time = f"{event['date']} {event['time']}"
            yield Event(
                shipment_id=0,
                event_time=event_time,
                event_description=event["evtDscr"],
                raw_event=json.dumps(event),
            )

    def supported_carriers(self):
        return [
            ("gls", 100),
        ]


tracker = GLS
