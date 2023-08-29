from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

from alembic.config import Config
from alembic import command

import json
import time

from pathlib import Path

Base = declarative_base()


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    tracking_number = Column(String)
    carrier = Column(String)
    description = Column(String)

    events = relationship("Event")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"))
    event_time = Column(String)
    event_description = Column(String)
    raw_event = Column(String)


class Database:
    def __init__(self, database_uri):
        self.engine = create_engine(database_uri)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        self.run_migrations()

    def create_shipment(self, tracking_number, carrier, description=""):
        new_shipment = Shipment(
            tracking_number=tracking_number, carrier=carrier, description=description
        )
        self.session.add(new_shipment)
        self.session.commit()

    def update_shipment(self, tracking_number, carrier, description=""):
        shipment = self.get_shipment(tracking_number)
        if shipment:
            shipment.carrier = carrier
            shipment.description = description
            self.session.commit()
        else:
            raise ValueError(f"Shipment {tracking_number} does not exist")

    def disable_shipment(self, tracking_number):
        shipment = self.get_shipment(tracking_number)
        if shipment:
            shipment.carrier = ""
            self.session.commit()
        else:
            raise ValueError(f"Shipment {tracking_number} does not exist")

    def get_shipment(self, tracking_number):
        shipment = (
            self.session.query(Shipment)
            .filter(Shipment.tracking_number == tracking_number)
            .first()
        )
        return shipment

    def get_shipments(self):
        shipments = self.session.query(Shipment).all()
        return shipments

    def create_event(self, shipment_id, event_time, event_description, raw_event):
        if isinstance(raw_event, dict):
            raw_event = json.dumps(raw_event)

        new_event = Event(
            shipment_id=shipment_id,
            event_time=event_time,
            event_description=event_description,
            raw_event=raw_event,
        )
        self.write_event(new_event)

    def write_event(self, event):
        self.session.add(event)
        self.session.commit()

    def get_shipment_events(self, shipment_id):
        shipment = (
            self.session.query(Shipment).filter(Shipment.id == shipment_id).first()
        )
        return shipment.events if shipment else None

    def get_latest_event(self, shipment_id):
        event = (
            self.session.query(Event)
            .filter(Event.shipment_id == shipment_id)
            .order_by(Event.event_time.desc())
            .first()
        )
        return event

    def make_migration(self, message):
        alembic_cfg = Config(Path(__file__).parent.parent / "alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", self.engine.url.__to_string__(hide_password=False))
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        alembic_cfg.set_main_option("script_location", str(migrations_dir))
        command.revision(alembic_cfg, message=message, autogenerate=True)

    def run_migrations(self):
        alembic_cfg = Config(Path(__file__).parent.parent / "alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", self.engine.url.__to_string__(hide_password=False))
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        alembic_cfg.set_main_option("script_location", str(migrations_dir))
        command.upgrade(alembic_cfg, "head")