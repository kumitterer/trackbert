from .base import BaseTracker
from ..classes.database import Event

import json

from datetime import datetime

from dpdtrack.classes.api import DPD as DPDAPI


class DPD(BaseTracker):
    def __init__(self, *args, **kwargs):
        pass

    def get_status(self, tracking_number, carrier):
        api = DPDAPI()
        status = api.tracking(tracking_number)
        
        events = status["data"][0]["lifecycle"]["entries"]

        for event in events:
            if "depotData" in event and event["depotData"] is not None:
                event_location = f"[{', '.join(event['depotData'])}] "
            else:
                event_location = ""

            event_timestamp = datetime.strptime(event["datetime"], "%Y%m%d%H%M%S")
            event_time = event_timestamp.strftime("%Y-%m-%d %H:%M:%S")

            yield Event(
                shipment_id=0,
                event_time=event_time,
                event_description=f"{event_location}{event['state']['text']}",
                raw_event=json.dumps(event),
            )

    def supported_carriers(self):
        return [
            ("dpd", 100, "DPD (Austria)"),
        ]


tracker = DPD
