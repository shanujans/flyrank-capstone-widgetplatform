"""
Seed script — creates demo data against a RUNNING instance of the API.

Usage:
    python scripts/seed.py [base_url]

Default base_url is http://localhost:8000. Safe to re-run: if the demo
tenant already exists, it just logs in instead of re-registering.
"""
import sys
import time

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
DEMO_EMAIL = "demo@acmebakery.com"
DEMO_PASSWORD = "demo-password-123"


def wait_for_api(client: httpx.Client, attempts: int = 20) -> None:
    for _ in range(attempts):
        try:
            resp = client.get("/health")
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise SystemExit(f"API at {BASE_URL} never became healthy — is it running?")


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        print(f"Waiting for API at {BASE_URL} ...")
        wait_for_api(client)

        print(f"Registering demo tenant {DEMO_EMAIL} ...")
        register = client.post("/auth/register", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        if register.status_code == 201:
            print("  created.")
        elif register.status_code == 400:
            print("  already exists, continuing.")
        else:
            raise SystemExit(f"Unexpected register response: {register.status_code} {register.text}")

        login = client.post("/auth/login", data={"username": DEMO_EMAIL, "password": DEMO_PASSWORD})
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("Creating demo widget ...")
        widget = client.post(
            "/widgets",
            headers=headers,
            json={
                "type": "signup_form",
                "title": "Join our newsletter",
                "description": "Fresh bread news, weekly.",
                "button_text": "Sign up",
                "fields": [
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                    {"name": "name", "label": "Name", "type": "text", "required": False},
                ],
            },
        )
        widget.raise_for_status()
        widget_id = widget.json()["id"]
        print(f"  widget id: {widget_id}")

        embed = client.get(f"/widgets/{widget_id}/embed", headers=headers)
        print(f"  embed snippet: {embed.json()['snippet']}")

        print("Posting a few sample submissions ...")
        for email, name in [
            ("visitor1@example.com", "Ada"),
            ("visitor2@example.com", "Grace"),
            ("visitor3@example.com", ""),
        ]:
            sub = client.post(
                f"/public/widgets/{widget_id}/submissions",
                json={"data": {"email": email, "name": name}, "hp_field": ""},
            )
            sub.raise_for_status()

        overview = client.get("/dashboard/overview", headers=headers)
        print(f"  dashboard overview: {overview.json()}")

        print("\nDemo login:")
        print(f"  email:    {DEMO_EMAIL}")
        print(f"  password: {DEMO_PASSWORD}")
        print(f"  widget:   {widget_id}")
        print("\nSeed complete.")


if __name__ == "__main__":
    main()
