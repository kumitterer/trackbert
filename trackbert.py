from pykeydelivery import KeyDelivery
from pathlib import Path
import json
import time
import subprocess
import argparse
import logging
from typing import Tuple, Never, Optional

from classes.database import Database
from classes.tracker import Tracker


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-number", "-n", type=str, required=False)
    parser.add_argument("--carrier", "-c", type=str, required=False)
    parser.add_argument("--description", "-d", type=str, required=False)
    parser.add_argument("--timeout", "-t", type=int, required=False, default=30, help="Notification timeout in seconds")

    args = parser.parse_args()

    tracker = Tracker()

    if args.tracking_number is not None and args.carrier is not None:
        db = Database('sqlite:///trackbert.db')
        db.create_shipment(args.tracking_number, args.carrier, args.description)
        print(f"Created shipment for {args.tracking_number} with carrier {args.carrier}")
        exit(0)

    if args.tracking_number is not None:
        print("You must specify a carrier with -c")
        exit(1)

    tracker.start()
