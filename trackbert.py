from pykeydelivery import KeyDelivery

import sqlite3
import json
import time
import subprocess
import argparse
import logging

from typing import Tuple, Never

# Print date and time and level with message
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

def notify(title: str, message: str):
    """Send a desktop notification

    If notify-send is not found, this function will do nothing.

    Args:
        title (str): The title of the notification
        message (str): The message of the notification
    """

    logging.debug(f"Sending notification: {title} - {message}")

    try:
        subprocess.run(
            [
                "notify-send",
                title,
                message,
                # TODO: Look into other options, like adding an icon
            ]
        )

    except FileNotFoundError:
        # If notify-send is not found, do nothing
        logging.warning("notify-send not found, not sending notification")


def create_shipment(db: sqlite3.Connection, tracking_number: str, carrier: str, description: str = ""):
    """Create a shipment in the database

    Args:
        db (sqlite3.Connection): The database connection
        tracking_number (str): The tracking number
        carrier (str): The carrier slug (e.g. "ups", "austrian_post")
        description (str, optional): A description for the shipment, displayed in place of the tracking number in notifications. Defaults to "".
    """

    logging.debug(f"Creating shipment for {tracking_number} with carrier {carrier}")
    db.execute(
        "INSERT INTO shipments (tracking_number, carrier, description) VALUES (?, ?, ?)",
        (tracking_number, carrier, description),
    )
    db.commit()


def get_shipment(db: sqlite3.Connection, tracking_number: str) -> Tuple[int, str, str, str]:
    """Get a shipment from the database

    Args:
        db (sqlite3.Connection): The database connection
        tracking_number (str): The tracking number

    Returns:
        Tuple[int, str, str, str]: The shipment (id, tracking_number, carrier, description)
    """

    logging.debug(f"Getting shipment for {tracking_number}")
    cur = db.cursor()
    cur.execute("SELECT * FROM shipments WHERE tracking_number = ?", (tracking_number,))
    return cur.fetchone()


def get_shipments(db: sqlite3.Connection) -> Tuple[Tuple[int, str, str, str]]:
    """Get all shipments from the database

    Args:
        db (sqlite3.Connection): The database connection

    Returns:
        Tuple[Tuple[int, str, str, str]]: All shipments (id, tracking_number, carrier, description)
    """

    logging.debug(f"Getting all shipments")
    cur = db.cursor()
    cur.execute("SELECT * FROM shipments")
    return cur.fetchall()


def get_shipment_events(db, shipment_id) -> Tuple[Tuple[int, int, str, str, str]]:
    """Get all events for a shipment from the database

    Args:
        db (sqlite3.Connection): The database connection
        shipment_id (int): The shipment id

    Returns:
        Tuple[Tuple[int, int, str, str, str]]: All events for the shipment (id, shipment_id, event_time, event_description, raw_event)
    """

    logging.debug(f"Getting events for shipment {shipment_id}")
    cur = db.cursor()
    cur.execute("SELECT * FROM events WHERE shipment_id = ?", (shipment_id,))
    return cur.fetchall()


def create_event(
    db,
    shipment_id,
    event_time,
    event_description,
    raw_event,
):
    """Create an event for a shipment in the database

    Args:
        db (sqlite3.Connection): The database connection
        shipment_id (int): The shipment id
        event_time (str): The event time
        event_description (str): The event description
        raw_event (str): The raw event
    """

    logging.debug(f"Creating event for shipment {shipment_id}: {event_description} - {event_time}")
    db.execute(
        "INSERT INTO events (shipment_id, event_time, event_description, raw_event) VALUES (?, ?, ?, ?)",
        (
            shipment_id,
            event_time,
            event_description,
            json.dumps(raw_event),
        ),
    )
    db.commit()


def get_latest_event(db, shipment_id) -> Tuple[int, int, str, str, str]:
    """Get the latest event for a shipment from the database

    Args:
        db (sqlite3.Connection): The database connection
        shipment_id (int): The shipment id

    Returns:
        Tuple[int, int, str, str, str]: The latest event (id, shipment_id, event_time, event_description, raw_event)
    """

    logging.debug(f"Getting latest event for shipment {shipment_id}")
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM events WHERE shipment_id = ? ORDER BY event_time DESC LIMIT 1",
        (shipment_id,),
    )
    return cur.fetchone()


def initialize_db(db):
    """Initialize the database - create tables if they don't exist

    Args:
        db (sqlite3.Connection): The database connection
    """

    logging.debug("Initializing database")
    db.execute(
        "CREATE TABLE IF NOT EXISTS shipments (id INTEGER PRIMARY KEY AUTOINCREMENT, tracking_number TEXT, carrier TEXT, description TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id INTEGER, event_time TEXT, event_description TEXT, raw_event TEXT, FOREIGN KEY(shipment_id) REFERENCES shipments(id))"
    )
    db.commit()


def get_db(path: str = "trackbert.db"):
    """Get a database connection

    Args:
        path (str, optional): The path to the database file. Defaults to "trackbert.db" in the current directory.

    Returns:
        sqlite3.Connection: The database connection
    """

    logging.debug("Connecting to database")
    db = sqlite3.connect(path)
    initialize_db(db)
    return db


def start_loop(db: sqlite3.Connection, api: KeyDelivery) -> Never:
    """Start the main loop

    Args:
        db (sqlite3.Connection): The database connection
        api (KeyDelivery): The KeyDelivery API object
    """

    logging.debug("Starting loop")
    while True:
        for shipment in get_shipments(db):
            shipment_id = shipment[0]
            tracking_number = shipment[1]
            carrier = shipment[2]
            description = shipment[3]

            logging.debug(f"Checking shipment {tracking_number} with carrier {carrier}")

            latest_known_event = get_latest_event(db, shipment_id)
            all_events = api.realtime(carrier, tracking_number)

            try:
                logging.debug(f"Got events for {tracking_number}: {len(all_events)}")
            except KeyError:
                print(f"Error getting events for {tracking_number}: {all_events}")
                continue

            for event in all_events["data"]["items"]:
                if latest_known_event is None or event["time"] > latest_known_event[3]:
                    create_event(
                        db,
                        shipment_id,
                        event["time"],
                        event["context"],
                        event,
                    )

                    logging.info(f"New event for {tracking_number}: {event['context']} - {event['time']}")
                    notify(f"New event for {description or tracking_number}", event["context"] + " - " + event["time"])

        time.sleep(300)


def main() -> Never:
    """Main function - get the database connection, create the KeyDelivery API object, and start the main loop"""

    db = get_db()
    api = KeyDelivery.from_config("config.ini")
    notify("Trackbert", "Starting up")
    start_loop(db, api)


if __name__ == "__main__":
    # Parse command line arguments
    
    parser = argparse.ArgumentParser()

    parser.add_argument("--tracking-number", "-n", type=str, required=False)
    parser.add_argument("--carrier", "-c", type=str, required=False)
    parser.add_argument("--description", "-d", type=str, required=False)
    args = parser.parse_args()

    # If the user specified a tracking number and carrier, create a shipment and exit

    if args.tracking_number is not None and args.carrier is not None:
        db = get_db()
        create_shipment(db, args.tracking_number, args.carrier, args.description)
        print(f"Created shipment for {args.tracking_number} with carrier {args.carrier}")
        exit(0)

    # If the user specified a tracking number but not a carrier, error out

    if args.tracking_number is not None:
        print("You must specify a carrier with -c")
        exit(1)

    # If no arguments were specified, start the main loop

    main()
