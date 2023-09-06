import logging
import subprocess
import time
import importlib
import asyncio
import sqlalchemy.exc

from pathlib import Path
from typing import Optional, Tuple, Never
from os import PathLike
from configparser import ConfigParser

from .database import Database
from ..trackers.base import BaseTracker


class Tracker:
    loop_interval = 60
    loop_timeout = 30

    def __init__(self, config: Optional[PathLike] = None):
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            level=logging.WARN,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self._pre_start(config)

        self.find_apis()

    def find_apis(self):
        logging.debug("Finding APIs")

        self.apis = []

        for api in Path(__file__).parent.parent.glob("trackers/*.py"):
            if api.name in ("__init__.py", "base.py"):
                continue

            logging.debug(f"Found API {api.stem}")

            try:
                module = importlib.import_module(f"trackbert.trackers.{api.stem}")
            except:
                logging.error(f"Error loading class {api.stem}")

            if "tracker" in module.__dict__:
                tracker = module.tracker
                logging.debug(f"Found tracker {api.stem}")
                try:
                    api = tracker(config=self.config_path)
                    carriers = api.supported_carriers()

                    for carrier in carriers:
                        self.apis.append((carrier[0], carrier[1], api, (carrier[2] if len(carrier) > 2 else None)))
                except Exception as e:
                    logging.error(f"Error loading tracker {api.__class__.__name__}: {e}")

    def query_api(self, tracking_number: str, carrier: str) -> list:
        logging.debug(f"Querying API for {tracking_number} with carrier {carrier}")

        for api_entry in sorted(self.apis, key=lambda x: x[1], reverse=True):
            api_carrier = api_entry[0]
            priority = api_entry[1]
            api = api_entry[2]
            name = api_entry[3] if len(api_entry) > 3 else None

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

    def notify_event(self, shipment, event, critical=False) -> None:
        logging.info(
            f"New event for {shipment.tracking_number}: {event.event_description} - {event.event_time}"
        )
        self.notify(
            f"New event for {shipment.description or shipment.tracking_number}",
            event.event_description + " - " + event.event_time,
            urgency="critical" if critical else "normal",
        )

    def process_shipment(self, shipment) -> None:
        if not shipment.carrier:
            logging.info(
                f"Shipment {shipment.tracking_number} has no carrier, skipping"
            )
            return

        logging.debug(
            f"Checking shipment {shipment.tracking_number} with carrier {shipment.carrier}"
        )

        latest_known_event = self.db.get_latest_event(shipment.id)

        try:
            events = self.query_api(shipment.tracking_number, shipment.carrier)
        except Exception as e:
            logging.exception(f"Error querying API for {shipment.tracking_number}")
            return

        events = sorted(events, key=lambda x: x.event_time)

        if not events:
            logging.debug(f"No events found for {shipment.tracking_number}")
            return

        if latest_known_event:
            logging.debug(
                f"Latest known event for {shipment.tracking_number}: {latest_known_event.event_description} - {latest_known_event.event_time}"
            )
        else:
            logging.debug(f"No known events for {shipment.tracking_number}")

        logging.debug(
            f"Latest upstream event for {shipment.tracking_number}: {events[-1].event_description} - {events[-1].event_time}"
        )

        for event in events:
            if (
                latest_known_event is None
                or event.event_time > latest_known_event.event_time
            ):
                event.shipment_id = shipment.id
                self.db.write_event(event)
                self.notify_event(shipment, event, event == events[-1])

    def start_loop(self) -> Never:
        logging.debug("Starting loop")

        while True:
            try:
                for shipment in self.db.get_shipments():
                    self.process_shipment(shipment)

                time.sleep(self.loop_interval)

            except sqlalchemy.exc.TimeoutError:
                logging.warning("Database timeout while processing shipments")
                self.db.engine.dispose()

            except KeyboardInterrupt:
                logging.info("Keyboard interrupt, exiting")
                exit(0)

            except Exception as e:
                logging.exception(f"Unknown error in loop: {e}")

    async def start_loop_async(self) -> Never:
        logging.debug("Starting loop")

        loop = asyncio.get_running_loop()

        while True:
            tasks = []
            for shipment in self.db.get_shipments():
                task = asyncio.wait_for(
                    asyncio.to_thread(self.process_shipment, shipment),
                    timeout=self.loop_timeout,
                )
                tasks.append(task)

            try:
                await asyncio.gather(*tasks)

            except asyncio.TimeoutError:
                logging.warning("Timeout while processing shipments")

            except sqlalchemy.exc.TimeoutError:
                logging.warning("Database timeout while processing shipments")

            except (KeyboardInterrupt, asyncio.CancelledError):
                logging.info("Keyboard interrupt, exiting")
                exit(0)

            except Exception as e:
                logging.exception(f"Unknown error in loop: {e}")

            await asyncio.sleep(self.loop_interval)

    def _pre_start(self, config: Optional[PathLike] = None):
        self.config_path = config

        parser = ConfigParser()
        parser.read(config or [])

        self.debug = parser.getboolean("Trackbert", "debug", fallback=False)

        if self.debug:
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)

        self.database_uri = parser.get(
            "Trackbert", "database", fallback="sqlite:///trackbert.db"
        )
        self.db = Database(self.database_uri)

        self.loop_interval = parser.getint("Trackbert", "interval", fallback=60)

    def start(self, config: Optional[PathLike] = None):
        self.notify("Trackbert", "Starting up")
        self.start_loop()

    async def start_async(self, config: Optional[PathLike] = None):
        self.notify("Trackbert", "Starting up")
        await self.start_loop_async()
