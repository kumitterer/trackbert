from pykeydelivery import KeyDelivery
from pathlib import Path
import json
import time
import subprocess
import argparse
import logging
import asyncio
from typing import Tuple, Never, Optional

from .classes.database import Database
from .classes.tracker import Tracker

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-number", "-n", type=str, required=False)
    parser.add_argument("--carrier", "-c", type=str, required=False)
    parser.add_argument("--description", "-d", type=str, required=False)
    parser.add_argument(
        "--update",
        "-u",
        action="store_true",
        required=False,
        help="Update existing shipment",
    )
    parser.add_argument(
        "--disable",
        "-D",
        action="store_true",
        required=False,
        help="Disable existing shipment",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        required=False,
        default=30,
        help="Notification timeout in seconds",
    )

    args = parser.parse_args()

    db = Database("sqlite:///trackbert.db")

    if args.tracking_number is not None and args.carrier is not None:
        if shipment := db.get_shipment(args.tracking_number) and not args.update:
            print(f"Shipment {args.tracking_number} already exists. Use -u to update.")
            exit(1)

        if shipment:
            db.update_shipment(args.tracking_number, args.carrier, args.description)
            print(
                f"Updated shipment for {args.tracking_number} with carrier {args.carrier}"
            )
        else:
            db.create_shipment(args.tracking_number, args.carrier, args.description)
            print(
                f"Created shipment for {args.tracking_number} with carrier {args.carrier}"
            )

        exit(0)

    if args.tracking_number is not None:
        if args.disable:
            if not db.get_shipment(args.tracking_number):
                print(f"Shipment {args.tracking_number} does not exist.")
                exit(1)
            db.disable_shipment(args.tracking_number)
            print(f"Disabled shipment for {args.tracking_number}")
            exit(0)

        print("You must specify a carrier with -c")
        exit(1)

    tracker = Tracker()
    asyncio.run(tracker.start_async())

if __name__ == "__main__":
    main()