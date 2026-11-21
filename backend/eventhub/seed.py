"""Demo data so the app looks alive on first run."""
import random
import secrets
from datetime import datetime, timedelta, timezone

from . import auth
from .db import get_store

ADMIN = {"email": "admin@eventhub.test", "password": "Admin@123", "name": "Aarav Mehta"}
DEMO = {"email": "user@eventhub.test", "password": "User@1234", "name": "Diya Shah"}

# (title, category, city, venue, days_from_now, hour, price, capacity, filled, description)
EVENTS = [
    ("Cloud Native Summit 2026", "Technology", "Bengaluru", "Palace Grounds Convention Hall", 3, 9, 1499, 120, 0.72,
     "A full day on Kubernetes, serverless and platform engineering, with talks from teams running real production systems."),
    ("Serverless Night: Build on AWS", "Technology", "Surat", "SVNIT Auditorium", 1, 17, 0, 60, 0.88,
     "Hands-on evening workshop. Build an API with Lambda, API Gateway and DynamoDB and leave with a working project."),
    ("Monsoon Indie Music Fest", "Music", "Mumbai", "Mehboob Studio Lawns", 9, 16, 899, 150, 0.55,
     "Twelve independent bands, two stages and a food court. Bring a friend and your dancing shoes."),
    ("Startup Pitch Friday", "Business", "Ahmedabad", "IIM-A Auditorium", 6, 15, 299, 80, 0.4,
     "Ten early-stage founders pitch to a panel of investors. Networking tea follows."),
    ("City Half Marathon", "Sports", "Surat", "Riverfront Promenade", 14, 5, 500, 200, 0.62,
     "21 km along the river. Chip timing, hydration points and finisher medals for everyone."),
    ("Watercolour Weekend Workshop", "Arts", "Pune", "Kala Ghar Studio", 5, 11, 650, 25, 1.0,
     "Two relaxed days of landscapes with a working painter. Materials included."),
    ("Street Food Trail & Tasting", "Food", "Surat", "Rander Old Market", 4, 18, 350, 60, 0.35,
     "A guided walk through eight stalls, with stories behind each recipe."),
    ("Intro to Machine Learning, Bootcamp", "Education", "Hyderabad", "T-Hub", 11, 10, 799, 60, 0.5,
     "From linear regression to a deployed model in one day. Laptop required."),
    ("Neighbourhood Clean-up Drive", "Community", "Surat", "Dumas Beach Gate 2", 2, 7, 0, 100, 0.45,
     "Gloves and bags provided. We finish with breakfast for every volunteer."),
    ("Product Design Meetup", "Business", "Bengaluru", "91springboard, Koramangala", 7, 18, 0, 50, 0.7,
     "Lightning talks on design systems, research and shipping with engineers."),
    ("Classical Evening: Sitar & Tabla", "Music", "Ahmedabad", "Tagore Hall", 12, 19, 450, 120, 0.3,
     "An unhurried evening of raga with two celebrated artists."),
    ("Hack the Campus 24h", "Technology", "Mumbai", "IIT Bombay, Kresit", 18, 10, 0, 100, 0.2,
     "Build something useful in 24 hours. Mentors, snacks and prizes included."),
]

FIRST = ["Isha", "Rohan", "Meera", "Kabir", "Anaya", "Vivaan", "Tara", "Neel", "Sana", "Arjun",
         "Riya", "Dev", "Kiara", "Yash", "Pooja", "Harsh"]
LAST = ["Patel", "Desai", "Shah", "Joshi", "Nair", "Rao", "Gupta", "Verma"]


def seed(force=False):
    store = get_store()
    if not force and not store.is_empty():
        return False
    rng = random.Random(7)
    ist = timezone(timedelta(hours=5, minutes=30))
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    local_base = base.astimezone(ist)

    users = {}
    for role, spec in (("admin", ADMIN), ("participant", DEMO)):
        existing = store.get_user_by_email(spec["email"])
        if existing:
            users[role] = existing
            continue
        users[role] = store.create_user({
            "id": "usr_" + secrets.token_hex(6), "email": spec["email"], "name": spec["name"],
            "role": role, "password_hash": auth.hash_password(spec["password"]),
            "created_at": base.isoformat(timespec="seconds"),
        })

    for title, category, city, venue, days, hour, price, capacity, fill, desc in EVENTS:
        # Hours above are local (IST) wall-clock times; store everything in UTC.
        start = (local_base + timedelta(days=days)).replace(hour=hour, minute=0).astimezone(timezone.utc)
        end = start + timedelta(hours=4 if price else 3)
        event = {
            "id": "evt_" + secrets.token_hex(5), "title": title, "category": category,
            "description": desc, "venue": venue, "city": city,
            "start": start.isoformat(timespec="seconds"), "end": end.isoformat(timespec="seconds"),
            "price": price, "capacity": capacity, "registered": 0,
            "organizer": ADMIN["name"], "image": "", "created_by": users["admin"]["id"],
            "created_at": base.isoformat(timespec="seconds"),
        }
        store.put_event(event)
        for i in range(int(capacity * fill)):
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if not store.reserve_seat(event["id"]):
                break
            stamp = (base - timedelta(days=rng.randint(0, 6), hours=rng.randint(0, 20)))
            store.put_registration({
                "id": "reg_" + secrets.token_hex(6), "event_id": event["id"],
                "user_id": f"seed_{event['id']}_{i}", "user_email": f"guest{i}@example.com",
                "user_name": name, "ticket_code": "EH-" + secrets.token_hex(3).upper(),
                "status": "confirmed", "reminded": False,
                "created_at": stamp.isoformat(timespec="seconds"),
            })
        # register the demo user for the first two events so "My tickets" isn't empty
        if title in ("Serverless Night: Build on AWS", "Street Food Trail & Tasting"):
            if store.reserve_seat(event["id"]):
                store.put_registration({
                    "id": "reg_" + secrets.token_hex(6), "event_id": event["id"],
                    "user_id": users["participant"]["id"], "user_email": DEMO["email"],
                    "user_name": DEMO["name"], "ticket_code": "EH-" + secrets.token_hex(3).upper(),
                    "status": "confirmed", "reminded": False, "created_at": base.isoformat(timespec="seconds"),
                })
    return True


if __name__ == "__main__":
    print("Seeded." if seed(force=True) else "Database already has data.")
