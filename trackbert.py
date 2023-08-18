from pykeydelivery import KeyDelivery

import sqlite3
import json
import time
import subprocess
import argparse
import logging

# Print date and time and level with message
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

def notify(title, message):
    logging.debug(f"Sending notification: {title} - {message}")
    try:
        subprocess.run(
            [
                "notify-send",
                title,
                message,
            ]
        )
    except FileNotFoundError:
        logging.warning("notify-send not found, not sending notification")


def create_shipment(db, tracking_number: str, carrier: str, description=""):
    logging.debug(f"Creating shipment for {tracking_number} with carrier {carrier}")
    db.execute(
        "INSERT INTO shipments (tracking_number, carrier, description) VALUES (?, ?, ?)",
        (tracking_number, carrier, description),
    )
    db.commit()


def get_shipment(db: sqlite3.Connection, tracking_number: str):
    logging.debug(f"Getting shipment for {tracking_number}")
    cur = db.cursor()
    cur.execute("SELECT * FROM shipments WHERE tracking_number = ?", (tracking_number,))
    return cur.fetchone()


def get_shipments(db: sqlite3.Connection):
    logging.debug(f"Getting all shipments")
    cur = db.cursor()
    cur.execute("SELECT * FROM shipments")
    return cur.fetchall()


def get_shipment_events(db, shipment_id):
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


def get_latest_event(db, shipment_id):
    logging.debug(f"Getting latest event for shipment {shipment_id}")
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM events WHERE shipment_id = ? ORDER BY event_time DESC LIMIT 1",
        (shipment_id,),
    )
    return cur.fetchone()


def initialize_db(db):
    logging.debug("Initializing database")
    db.execute(
        "CREATE TABLE IF NOT EXISTS shipments (id INTEGER PRIMARY KEY AUTOINCREMENT, tracking_number TEXT, carrier TEXT, description TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id INTEGER, event_time TEXT, event_description TEXT, raw_event TEXT, FOREIGN KEY(shipment_id) REFERENCES shipments(id))"
    )
    db.commit()


def get_db():
    logging.debug("Connecting to database")
    db = sqlite3.connect("trackbert.db")
    initialize_db(db)
    return db


def start_loop(db, api: KeyDelivery):
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


def main():
    db = get_db()
    api = KeyDelivery.from_config("config.ini")
    notify("Trackbert", "Starting up")
    start_loop(db, api)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--tracking-number", "-n", type=str, required=False)
    parser.add_argument("--carrier", "-c", type=str, required=False)
    parser.add_argument("--description", "-d", type=str, required=False)
    args = parser.parse_args()

    if args.tracking_number is not None and args.carrier is not None:
        db = get_db()
        create_shipment(db, args.tracking_number, args.carrier, args.description)
        print(f"Created shipment for {args.tracking_number} with carrier {args.carrier}")
        exit(0)

    if args.tracking_number is not None:
        print("You must specify a carrier with -c")
        exit(1)

    main()
