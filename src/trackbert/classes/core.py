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
from .provider import BaseProvider


class Core:
    loop_interval: int = 60
    loop_timeout: int = 30

    config: Optional[ConfigParser] = None

    def __init__(self, config: Optional[PathLike] = None):
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            level=logging.WARN,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self._pre_start(config)
        self.notifiers = self.find_notifiers()
        self.providers = self.find_providers()

    def find_core_notifiers(self):
        logging.debug("Finding core notifiers")

        notifiers = []

        for notifier in Path(__file__).parent.parent.glob("notifiers/*.py"):
            if notifier.name in ("__init__.py", "base.py"):
                continue

            logging.debug(f"Considering notifier {notifier.stem}")

            try:
                module = importlib.import_module(f"trackbert.notifiers.{notifier.stem}")
            except Exception as e:
                logging.error(f"Error loading class {notifier.stem}: {e}")
                continue

            if "notifier" in module.__dict__:
                notifier_class = module.notifier
                logging.debug(f"Found notifier {notifier_class.__name__}")

                try:
                    if self.config and notifier_class.__name__ in self.config:
                        nconfig = self.config[notifier_class.__name__]
                    else:
                        nconfig = None

                    nobj = notifier_class(config=nconfig)

                    if nobj.enabled:
                        notifiers.append(nobj)

                except Exception as e:
                    logging.error(
                        f"Error loading notifier {notifier_class.__name__}: {e}"
                    )

        return notifiers

    def find_external_notifiers(self):
        # TODO: Implement external notifiers using entry points
        return []

    def find_notifiers(self):
        return self.find_core_notifiers() + self.find_external_notifiers()

    def find_core_providers(self):
        logging.debug("Finding core tracking providers")

        providers = []

        for provider in Path(__file__).parent.parent.glob("providers/*.py"):
            if provider.name in ("__init__.py", "base.py"):
                continue

            logging.debug(f"Considering provider {provider.stem}")

            try:
                module = importlib.import_module(f"trackbert.providers.{provider.stem}")
            except Exception as e:
                logging.error(f"Error loading class {provider.stem}: {e}")
                continue

            if "provider" in module.__dict__:
                provider_api = module.provider
                logging.debug(f"Found provider {provider_api.__name__}")
                try:
                    pobj = provider_api(config=self.config_path)
                    carriers = pobj.supported_carriers()

                    for carrier in carriers:
                        providers.append(
                            (
                                carrier[0],
                                carrier[1],
                                pobj,
                                (carrier[2] if len(carrier) > 2 else None),
                            )
                        )
                except Exception as e:
                    logging.error(
                        f"Error loading provider {provider.__class__.__name__}: {e}"
                    )

        return providers

    def find_external_providers(self):
        # TODO: Implement external providers using entry points
        return []

    def find_providers(self):
        return self.find_core_providers() + self.find_external_providers()

    def query_provider(self, tracking_number: str, carrier: str) -> list:
        logging.debug(f"Querying provider for {tracking_number} with carrier {carrier}")

        for api_entry in sorted(self.providers, key=lambda x: x[1], reverse=True):
            api_carrier = api_entry[0]
            priority = api_entry[1]
            provider = api_entry[2]
            name = api_entry[3] if len(api_entry) > 3 else None

            if api_carrier == "*" or api_carrier == carrier:
                logging.debug(
                    f"Using provider {provider.__class__.__name__} for {tracking_number} with carrier {carrier}"
                )
                return list(provider.get_status(tracking_number, carrier))

    def notify(self, title, message, urgent=False) -> None:
        for notifier in self.notifiers:
            notifier.notify(title, message, urgent)

    def notify_event(self, shipment, event, urgent=False) -> None:
        logging.info(
            f"New event for {shipment.tracking_number}: {event.event_description} - {event.event_time}"
        )
        self.notify(
            f"New event for {shipment.description or shipment.tracking_number}",
            event.event_description + " - " + event.event_time,
            urgent=urgent,
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
            events = self.query_provider(shipment.tracking_number, shipment.carrier)
        except Exception as e:
            logging.exception(
                f"Error querying provider for {shipment.tracking_number}: {e}"
            )
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

        self.config = ConfigParser()
        self.config.read(config or [])

        self.debug = self.config.getboolean("Trackbert", "debug", fallback=False)

        if self.debug:
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)

        self.database_uri = self.config.get(
            "Trackbert", "database", fallback="sqlite:///trackbert.db"
        )
        self.db = Database(self.database_uri)

        self.loop_interval = self.config.getint("Trackbert", "interval", fallback=60)

    def start(self, config: Optional[PathLike] = None):
        self.notify("Trackbert", "Starting up")
        self.start_loop()

    async def start_async(self, config: Optional[PathLike] = None):
        self.notify("Trackbert", "Starting up")
        await self.start_loop_async()
