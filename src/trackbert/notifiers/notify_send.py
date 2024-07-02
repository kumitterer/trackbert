from ..classes.notifier import BaseNotifier

import subprocess
import logging

from typing import Optional
from pathlib import Path


class NotifySend(BaseNotifier):
    def __init__(self, **kwargs):
        pass

    def notify(
        self,
        title: str,
        message: str,
        urgent: bool = False,
        timeout: Optional[int] = 5000,
    ) -> None:
        logging.debug(f"Sending notification: {title} - {message}")

        command = [
            "notify-send",
            "-a",
            "trackbert",
            "-u",
            "normal" if not urgent else "critical",
            "-i",
            str(Path(__file__).parent.parent / "assets" / "parcel-delivery-icon.webp"),
        ]

        if timeout and not urgent:
            command += ["-t", str(timeout)]

        command = command + [title, message]

        try:
            subprocess.run(command)

        except FileNotFoundError:
            logging.warning("notify-send not found, not sending notification")

    @property
    def enabled(self) -> bool:
        try:
            subprocess.run(["notify-send", "--help"], stdout=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            return False


notifier = NotifySend
