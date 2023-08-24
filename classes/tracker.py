import logging
import subprocess
import time
import importlib
from pathlib import Path
from typing import Optional, Tuple, Never

from .database import Database
from trackers.base import BaseTracker

from pykeydelivery import KeyDelivery


class Tracker:
    def __init__(self):
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            level=logging.DEBUG,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self.find_apis()

    def find_apis(self):
        logging.debug("Finding APIs")

        self.apis = []

        for api in Path(__file__).parent.parent.glob("trackers/*.py"):
            if api.name in ("__init__.py", "base.py"):
                continue

            logging.debug(f"Found API {api.stem}")

            module = importlib.import_module(f"trackers.{api.stem}")

            if "tracker" in module.__dict__:
                tracker = module.tracker
                logging.debug(f"Found tracker {api.stem}")
                try:
                    carriers = tracker.supported_carriers()
                    api = tracker()

                    for carrier, priority in carriers:
                        self.apis.append((carrier, priority, api))
                except:
                    logging.exception(f"Error loading tracker {name}")

    def query_api(self, tracking_number: str, carrier: str) -> list:
        logging.debug(f"Querying API for {tracking_number} with carrier {carrier}")

        for api_carrier, _, api in sorted(self.apis, key=lambda x: x[1], reverse=True):
            if api_carrier == "*" or api_carrier == carrier:
                logging.debug(
                    f"Using API {api.__class__.__name__} for {tracking_number} with carrier {carrier}"
                )
                return list(api.get_status(tracking_number, carrier))

    def notify(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        timeout: Optional[int] = 5000,
    ) -> None:
        logging.debug(f"Sending notification: {title} - {message}")

        command = [
            "notify-send",
            "-a",
            "trackbert",
            "-u",
            urgency,
            "-i",
            str(Path(__file__).parent.parent / "assets" / "parcel-delivery-icon.webp"),
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
                if not shipment.carrier:
                    logging.warning(
                        f"Shipment {shipment.tracking_number} has no carrier, skipping"
                    )
                    continue

                logging.debug(
                    f"Checking shipment {shipment.tracking_number} with carrier {shipment.carrier}"
                )

                latest_known_event = self.db.get_latest_event(shipment.id)

                events = self.query_api(shipment.tracking_number, shipment.carrier)
                events = sorted(events, key=lambda x: x.event_time, reverse=True)

                if latest_known_event:
                    logging.debug(
                        f"Latest known event for {shipment.tracking_number}: {latest_known_event.event_description} - {latest_known_event.event_time}"
                    )
                else:
                    logging.debug(f"No known events for {shipment.tracking_number}")

                logging.debug(
                    f"Latest upstream event for {shipment.tracking_number}: {events[0].event_description} - {events[0].event_time}"
                )

                latest = True

                for event in events:
                    if (
                        latest_known_event is None
                        or event.event_time > latest_known_event.event_time
                    ):
                        event.shipment_id = shipment.id
                        self.db.write_event(event)

                        logging.info(
                            f"New event for {shipment.tracking_number}: {event.event_description} - {event.event_time}"
                        )
                        self.notify(
                            f"New event for {shipment.description or shipment.tracking_number}",
                            event.event_description + " - " + event.event_time,
                            urgency="critical" if latest else "normal",
                        )

                        latest = False

            time.sleep(300)

    def start(self):
        self.db = Database("sqlite:///trackbert.db")
        self.notify("Trackbert", "Starting up")
        self.start_loop()
