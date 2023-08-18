from pykeydelivery import KeyDelivery

import sqlite3
import json
import time
import subprocess
import argparse


def notify(title, message):
    subprocess.run(
        [
            "notify-send",
            title,
            message,
        ]
    )


def create_shipment(db, tracking_number: str, carrier: str, description=""):
    db.execute(
        "INSERT INTO shipments (tracking_number, carrier, description) VALUES (?, ?, ?)",
        (tracking_number, carrier, description),
    )
    db.commit()


def get_shipment(db: sqlite3.Connection, tracking_number: str):
    cur = db.cursor()
    cur.execute("SELECT * FROM shipments WHERE tracking_number = ?", (tracking_number,))
    return cur.fetchone()


def get_shipments(db: sqlite3.Connection):
    cur = db.cursor()
    cur.execute("SELECT * FROM shipments")
    return cur.fetchall()


def get_shipment_events(db, shipment_id):
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
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM events WHERE shipment_id = ? ORDER BY event_time DESC LIMIT 1",
        (shipment_id,),
    )
    return cur.fetchone()


def initialize_db(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS shipments (id INTEGER PRIMARY KEY AUTOINCREMENT, tracking_number TEXT, carrier TEXT, description TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id INTEGER, event_time TEXT, event_description TEXT, raw_event TEXT, FOREIGN KEY(shipment_id) REFERENCES shipments(id))"
    )
    db.commit()


def get_db():
    db = sqlite3.connect("trackbert.db")
    initialize_db(db)
    return db


def start_loop(db, api: KeyDelivery):
    while True:
        for shipment in get_shipments(db):
            shipment_id = shipment[0]
            tracking_number = shipment[1]
            carrier = shipment[2]
            description = shipment[3]
            latest_known_event = get_latest_event(db, shipment_id)
            all_events = api.realtime(carrier, tracking_number)
            for event in all_events["data"]["items"]:
                if latest_known_event is None or event["time"] > latest_known_event[3]:
                    create_event(
                        db,
                        shipment_id,
                        event["time"],
                        event["context"],
                        event,
                    )
                    print(f"New event for {tracking_number}: {event['context']}")
                    notify(f"New event for {description}", event["context"])

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
