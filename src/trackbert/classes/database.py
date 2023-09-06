from sqlalchemy import Column, Integer, String, Boolean, create_engine, ForeignKey, event
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.ext.declarative import declarative_base

from alembic.config import Config
from alembic import command

import json
import time
import logging

from functools import wraps
from pathlib import Path

Base = declarative_base()


def with_session(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        session = self.session()
        try:
            result = func(self, session, *args, **kwargs)
            session.commit()
            return result
        except:
            session.rollback()
            raise

    return wrapper


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    tracking_number = Column(String)
    carrier = Column(String)
    description = Column(String)
    disabled = Column(Boolean, default=False)

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
        self.engine = create_engine(database_uri, pool_size=20, max_overflow=20)
        self.session = scoped_session(sessionmaker(bind=self.engine))

        event.listen(self.engine, "connect", lambda _, __: logging.debug("DB connected"))
        event.listen(self.engine, "close", lambda _, __: logging.debug("DB connection closed"))

        self.run_migrations()

    @with_session
    def create_shipment(self, session, tracking_number, carrier, description=""):
        new_shipment = Shipment(
            tracking_number=tracking_number, carrier=carrier, description=description
        )
        session.add(new_shipment)
        session.commit()

    @with_session
    def update_shipment(self, session, tracking_number, carrier, description=""):
        shipment = self.get_shipment(tracking_number)
        if shipment:
            shipment.carrier = carrier
            shipment.description = description
            session.commit()
        else:
            raise ValueError(f"Shipment {tracking_number} does not exist")

    @with_session
    def disable_shipment(self, session, tracking_number):
        shipment = self.get_shipment(tracking_number)
        if shipment:
            shipment.carrier = ""
            session.commit()
        else:
            raise ValueError(f"Shipment {tracking_number} does not exist")

    @with_session
    def get_shipment(self, session, tracking_number):
        shipment = (
            session.query(Shipment)
            .filter(Shipment.tracking_number == tracking_number)
            .first()
        )
        return shipment

    @with_session
    def get_shipments(self, session, ignore_disabled=True):
        shipments = session.query(Shipment).all()

        if ignore_disabled:
            shipments = [s for s in shipments if not s.disabled]

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

    @with_session
    def write_event(self, session, event):
        session.add(event)
        session.commit()

    @with_session
    def get_shipment_events(self, session, shipment_id):
        shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
        return shipment.events if shipment else None

    @with_session
    def get_latest_event(self, session, shipment_id):
        event = (
            session.query(Event)
            .filter(Event.shipment_id == shipment_id)
            .order_by(Event.event_time.desc())
            .first()
        )
        return event

    def make_migration(self, message):
        alembic_cfg = Config(Path(__file__).parent.parent / "alembic.ini")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", self.engine.url.__to_string__(hide_password=False)
        )
        migrations_dir = Path(__file__).parent.parent / "migrations"
        alembic_cfg.set_main_option("script_location", str(migrations_dir))
        command.revision(alembic_cfg, message=message, autogenerate=True)

    def run_migrations(self):
        alembic_cfg = Config(Path(__file__).parent.parent / "alembic.ini")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", self.engine.url.__to_string__(hide_password=False)
        )
        migrations_dir = Path(__file__).parent.parent / "migrations"
        alembic_cfg.set_main_option("script_location", str(migrations_dir))
        command.upgrade(alembic_cfg, "head")
