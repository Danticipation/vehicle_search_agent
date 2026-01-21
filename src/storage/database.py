import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    listings = relationship("Listing", back_populates="agent")

class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agents.id"))
    source: Mapped[str] = mapped_column(String)
    external_id: Mapped[str] = mapped_column(String, unique=True) # VIN or URL
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mileage: Mapped[Optional[int]] = mapped_column(Float, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Float, nullable=True)
    make: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON)
    first_seen: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)

    agent = relationship("Agent", back_populates="listings")

async def init_db(database_url: str):
    # asyncpg does not support 'sslmode' or 'channel_binding' in the connection string.
    # We strip these out and handle SSL via connect_args.
    if "?" in database_url:
        base_url, query = database_url.split("?", 1)
        params = query.split("&")
        # Filter out unsupported parameters
        filtered_params = [p for p in params if not p.startswith(("sslmode=", "channel_binding="))]
        database_url = base_url + ("?" + "&".join(filtered_params) if filtered_params else "")

    engine = create_async_engine(
        database_url, 
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"ssl": True} if "neon.tech" in database_url else {}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine

def get_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
