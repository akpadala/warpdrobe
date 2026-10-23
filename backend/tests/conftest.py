import io
import os
import sys
from pathlib import Path

import pytest

# Isolated settings for every test run: throwaway DB, no API key, rules-only pairings.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["PAIRINGS_PATH"] = "/nonexistent/pairings.json"
os.environ["FRONTEND_DIST"] = "/nonexistent"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import db as db_module  # noqa: E402
from app.main import app  # noqa: E402  (also registers all models on Base)
from app.db import Base  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def get_test_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_module.get_db] = get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def photo(color=(30, 40, 80), size=(400, 500)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def auth(client):
    r = client.post("/api/auth/register", json={"email": "Ana@Example.com", "name": "Ana", "password": "hunter2hunter2"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
