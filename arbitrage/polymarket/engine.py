from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings


def make_url(db_name: str = None) -> str:
    db = db_name or settings.db_name
    return (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{db}"
    )


engine = create_engine(make_url(), pool_pre_ping=True, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

# PolyMarket 专用 engine
polymarket_engine = create_engine(make_url(settings.db_polymarket), pool_pre_ping=True, echo=False, future=True)
