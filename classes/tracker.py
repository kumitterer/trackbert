import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, Never

from .database import Database

from pykeydelivery import KeyDelivery

class Tracker:
    def __init__(self):
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            level=logging.DEBUG,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def notify(self, title: str, message: str, urgency: str = "normal", timeout: Optional[int] = 5000) -> None:
        logging.debug(f"Sending notification: {title} - {message}")

        command = [
                    "notify-send",
                    "-a", "trackbert",
                    "-u", urgency,
                    "-i", str(Path(__file__).parent / "assets" / "parcel-delivery-icon.webp"),
                ]

        if timeout:
            command += ["-t", str(timeout)]

        command = command + [title, message]

        try:
            subprocess.run(command)

        except FileNotFoundError:
            logging.warning("notify-send not found, not sending notification")

    def start_loop(self) -> Never:
        logging.debug("Starting loop")
        while True:
            for shipment in self.db.get_shipments():
                shipment_id = shipment.id
                tracking_number = shipment.tracking_number
                carrier = shipment.carrier
                description = shipment.description

                logging.debug(f"Checking shipment {tracking_number} with carrier {carrier}")

                latest_known_event = self.db.get_latest_event(shipment_id)

                all_events = self.api.realtime(carrier, tracking_number)

                try:
                    logging.debug(f"Got events for {tracking_number}: {len(all_events['data']['items'])}")
                except KeyError:
                    print(f"Error getting events for {tracking_number}: {all_events}")
                    continue

                events = sorted(all_events["data"]["items"], key=lambda x: x["time"], reverse=True)

                if latest_known_event:
                    logging.debug(f"Latest known event for {tracking_number}: {latest_known_event.event_description} - {latest_known_event.event_time}")
                else:
                    logging.debug(f"No known events for {tracking_number}")

                logging.debug(f"Latest upstream event for {tracking_number}: {events[0]['context']} - {events[0]['time']}")

                latest = True

                for event in events:
                    if latest_known_event is None or event["time"] > latest_known_event.event_time:
                        self.db.create_event(
                            shipment_id,
                            event["time"],
                            event["context"],
                            event,
                        )

                        logging.info(f"New event for {tracking_number}: {event['context']} - {event['time']}")
                        self.notify(f"New event for {description or tracking_number}", event["context"] + " - " + event["time"], urgency="critical" if latest else "normal")

                        latest = False

            time.sleep(300)

    def start(self):
        self.db = Database('sqlite:///trackbert.db')
        self.api = KeyDelivery.from_config("config.ini")
        self.notify("Trackbert", "Starting up")
        self.start_loop()