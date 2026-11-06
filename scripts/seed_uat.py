#!/usr/bin/env python3
"""Create a realistic UAT data set through the running API (so it exercises the real KRA and M-Pesa paths).

Usage: python scripts/seed_uat.py [--base-url http://localhost:8000]
Prints the certificate numbers and security codes testers need for the verify scripts.
"""
import argparse
import sys
import time

import httpx

PASSWORD = "PermitPass!2026"
DATA = [  # (business, KRA PIN, steps)
    ("Kibanda Coffee House", "A051234567K", ["submit", "pay", "approve", "issue"]),
    ("Nyeri Fresh Produce", "P051234560C", ["submit", "pay", "approve", "issue"]),
    ("Mama Ngina Tailors", "A112233445D", ["submit", "pay"]),
    ("Rift Valley Hardware", "A223344556E", ["submit", "pay"]),
    ("Thika Tyres", "A334455667F", ["submit", "pay", "approve"]),
    ("Lamu Dhow Tours", "A445566778G", ["submit", "reject"]),
    ("Malindi Beach Hotel", "A556677889H", ["submit", "pay", "approve", "issue", "revoke"]),
    ("Kisumu Bike Repairs", "A667788990J", ["submit"]),
    ("Garissa Camels", "P778899001K", []),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    args = ap.parse_args()
    http = httpx.Client(base_url=args.base_url, timeout=15)

    def token(email):
        r = http.post("/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    citizen, officer = token("citizen@permitpass.test"), token("officer@permitpass.test")
    who = {"submit": citizen, "pay": citizen, "approve": officer, "issue": officer, "reject": officer, "revoke": officer}
    certs = []
    for name, pin, steps in DATA:
        r = http.post("/applications", json={"business_name": name, "kra_pin": pin}, headers=citizen)
        r.raise_for_status()
        app_id = r.json()["id"]
        for step in steps:
            body = {"phone": "0712345678"} if step == "pay" else {"reason": "UAT sample"} if step in ("reject", "revoke") else None
            http.post(f"/applications/{app_id}/{step}", json=body, headers=who[step]).raise_for_status()
            if step == "pay":   # wait for the M-Pesa (stub) callback
                for _ in range(30):
                    if http.get(f"/applications/{app_id}", headers=citizen).json()["state"] == "paid":
                        break
                    time.sleep(0.5)
                else:
                    print(f"payment for {name} did not settle; is WireMock running?", file=sys.stderr)
                    return 1
        if "issue" in steps:
            c = http.get(f"/applications/{app_id}/certificate", headers=citizen).json()
            certs.append((name, c["number"], c["signature"], "revoked" if "revoke" in steps else "valid"))
        print(f"  {name:<24} -> {(steps or ['draft'])[-1]}")
    print("\nCertificates for the verify scripts:")
    for name, number, sig, status in certs:
        print(f"  {name:<24} {number}  code {sig}  (expect: {status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
