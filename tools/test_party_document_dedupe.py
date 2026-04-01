#!/usr/bin/env python3
"""HTTP-only test: document-based dedupe for TMF632 Party (Individual).

Creates two Individuals with the same document number/type.
Expected behavior after wiring change:
- Second POST reuses the existing res.partner record
- The returned TMF id should therefore be the same.
"""

import json
import uuid
import requests

BASE = "http://localhost:8069"
H = {"Content-Type": "application/json", "Accept": "application/json"}


def post(path: str, payload: dict) -> dict:
    r = requests.post(BASE + path, headers=H, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def main():
    t = uuid.uuid4().hex[:6]
    doc_number = f"1-9-{t}"

    p1 = post("/tmf-api/partyManagement/v5/individual", {
        "@type": "Individual",
        "givenName": "Doc",
        "familyName": "Test",
        "document": {"type": "RUT", "number": doc_number},
    })

    p2 = post("/tmf-api/partyManagement/v5/individual", {
        "@type": "Individual",
        "givenName": "Doc2",
        "familyName": "Test2",
        "document": {"type": "RUT", "number": doc_number},
    })

    out = {
        "doc_number": doc_number,
        "p1_id": p1.get("id"),
        "p2_id": p2.get("id"),
        "same_id": p1.get("id") == p2.get("id"),
        "p1": p1,
        "p2": p2,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
