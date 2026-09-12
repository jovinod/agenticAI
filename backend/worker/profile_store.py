import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, UniqueConstraint, select

from db import engine


class TickerProfile(SQLModel, table=True):
    __tablename__ = "ticker_profiles"
    __table_args__ = (UniqueConstraint("ticker", "market"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True)
    market: str
    sector: str | None = None
    industry: str | None = None
    research_count: int = 1
    first_researched_at: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow
    )
    last_researched_at: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow
    )


SQLModel.metadata.create_all(engine)


def record_research(
    ticker: str, market: str, sector: str | None = None, industry: str | None = None
) -> TickerProfile:
    """Exact identity is (ticker, market) -- the same symbol can refer to
    different instruments across exchanges. A read followed by insert or
    update, not yet a database-native upsert."""
    now = datetime.datetime.utcnow()
    with Session(engine) as session:
        profile = session.exec(
            select(TickerProfile).where(
                TickerProfile.ticker == ticker, TickerProfile.market == market
            )
        ).first()

        if profile is None:
            profile = TickerProfile(
                ticker=ticker,
                market=market,
                sector=sector,
                industry=industry,
                research_count=1,
                first_researched_at=now,
                last_researched_at=now,
            )
        else:
            profile.research_count += 1
            profile.last_researched_at = now
            if sector is not None:
                profile.sector = sector
            if industry is not None:
                profile.industry = industry

        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile
