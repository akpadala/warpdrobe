from datetime import date

from tests.conftest import photo


def upload(client, auth, color, price=None):
    data = {"price": str(price)} if price is not None else {}
    r = client.post("/api/items", headers=auth, files={"photo": ("p.png", photo(color), "image/png")}, data=data)
    assert r.status_code == 200, r.text
    return r.json()


def test_register_login_and_me(client):
    r = client.post("/api/auth/register", json={"email": "a@b.co", "name": "A", "password": "short"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"email": "a@b.co", "name": "A", "password": "longenough"})
    assert r.status_code == 200
    assert client.post("/api/auth/register", json={"email": "A@b.co", "name": "A", "password": "longenough"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "a@b.co", "password": "nope-nope"}).status_code == 401
    token = client.post("/api/auth/login", json={"email": "A@B.co", "password": "longenough"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/me", headers=h).json()["email"] == "a@b.co"
    client.post("/api/auth/logout", headers=h)
    assert client.get("/api/me", headers=h).status_code == 401
    assert client.get("/api/items").status_code == 401


def test_upload_review_and_image(client, auth):
    item = upload(client, auth, (30, 40, 80), price=40)
    assert item["tag_source"] == "fallback" and item["color"] == "navy"
    assert client.get(item["image_url"]).headers["content-type"] == "image/jpeg"
    r = client.patch(f"/api/items/{item['id']}", headers=auth,
                     json={"category": "bottom", "formality": 4, "name": "navy trousers"})
    assert r.json()["tag_source"] == "user" and r.json()["category"] == "bottom"
    bad = client.post("/api/items", headers=auth, files={"photo": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400
    assert client.patch(f"/api/items/{item['id']}", headers=auth, json={"color": "chartreuse"}).status_code == 422


def test_items_are_private(client, auth):
    item = upload(client, auth, (240, 240, 240))
    other = client.post("/api/auth/register", json={"email": "b@b.co", "name": "B", "password": "longenough"}).json()
    h2 = {"Authorization": f"Bearer {other['token']}"}
    assert client.get("/api/items", headers=h2).json() == []
    assert client.delete(f"/api/items/{item['id']}", headers=h2).status_code == 404
    assert client.post("/api/outfits", headers=h2, json={"for_date": "2026-10-27", "item_ids": [item["id"]]}).status_code == 404


def make_closet(client, auth):
    specs = [
        dict(name="white shirt", category="top", color="white", formality=4, price=30),
        dict(name="grey hoodie", category="top", color="grey", formality=1, price=45),
        dict(name="navy trousers", category="bottom", color="navy", formality=4, price=60),
        dict(name="jeans", category="bottom", color="blue", formality=2, price=50),
        dict(name="loafers", category="shoes", color="black", formality=4, price=90),
    ]
    return [client.post("/api/items/manual", headers=auth, json=s).json() for s in specs]


def test_plan_outfit_wear_and_insights(client, auth):
    items = make_closet(client, auth)
    plan = client.get("/api/plan", headers=auth, params={"day": "2026-10-27", "formality": 4}).json()
    assert len(plan["suggestions"]) == 2
    top = plan["suggestions"][0]
    names = {i["name"] for i in top["items"]}
    assert {"white shirt", "navy trousers", "loafers"} <= names
    assert any("city" in w for w in plan["warnings"])

    ids = [i["id"] for i in top["items"]]
    o = client.post("/api/outfits", headers=auth, json={
        "for_date": "2026-10-27", "item_ids": ids, "engine_score": top["score"], "rank": 1, "worn": True}).json()
    client.patch(f"/api/outfits/{o['id']}", headers=auth, json={"rating": 5})
    # Saving the same day twice doesn't double-count wears.
    client.post("/api/outfits", headers=auth, json={"for_date": "2026-10-27", "item_ids": ids, "worn": True})

    by_name = {i["name"]: i for i in client.get("/api/items", headers=auth).json()}
    assert by_name["white shirt"]["wear_count"] == 1
    assert by_name["white shirt"]["cost_per_wear"] == 30
    assert by_name["loafers"]["last_worn"] == "2026-10-27"

    ins = client.get("/api/insights", headers=auth).json()
    assert ins["totals"]["items"] == 5 and ins["totals"]["wears_logged"] == 3
    assert {i["name"] for i in ins["never_worn"]} == {"grey hoodie", "jeans"}
    assert ins["next_buys"], "should suggest something to buy"
    # Highest cost per wear first: $90 loafers worn once beat $60 worn-once trousers and $50 unworn jeans.
    assert [i["name"] for i in ins["cost_per_wear"]][:2] == ["loafers", "navy trousers"]


def test_log_single_wear(client, auth):
    item = make_closet(client, auth)[0]
    r = client.post(f"/api/items/{item['id']}/wear", headers=auth, params={"on": date.today().isoformat()})
    assert r.json()["wear_count"] == 1


def test_settings_reject_bad_calendar(client, auth):
    r = client.patch("/api/me", headers=auth, json={"ics_url": "https://example.com/cal.ics"})
    assert r.status_code == 400
    r = client.patch("/api/me", headers=auth, json={"latitude": 35.9, "longitude": -79.05})
    assert r.json()["location_name"] == "Current location"


def test_admin_metrics(client, auth):
    assert client.get("/api/admin/metrics", headers=auth).status_code == 403
    admin = client.post("/api/auth/register", json={"email": "admin@example.com", "name": "Ad", "password": "longenough"}).json()
    assert admin["user"]["is_admin"]
    m = client.get("/api/admin/metrics", headers={"Authorization": f"Bearer {admin['token']}"}).json()
    assert m["users"] == 2 and m["active_7d"] == 2


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True, "tagger": "fallback", "pairings": "rules"}
