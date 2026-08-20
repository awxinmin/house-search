"""Persistent state and listings store (JSON-backed)."""

import json
import os
from config import STATE_FILE, LISTINGS_FILE


def _mkdir():
    os.makedirs("data", exist_ok=True)


# ── State (run history) ───────────────────────────────────────────────────────

def load_state() -> dict:
    _mkdir()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_run_date": None, "is_first_run": True, "sent_listing_ids": []}


def save_state(state: dict):
    _mkdir()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


# ── Listings store ────────────────────────────────────────────────────────────

def load_listings() -> dict:
    _mkdir()
    if os.path.exists(LISTINGS_FILE):
        with open(LISTINGS_FILE) as f:
            return json.load(f)
    return {}


def save_listings(store: dict):
    _mkdir()
    with open(LISTINGS_FILE, "w") as f:
        json.dump(store, f, indent=2, default=str)


def upsert_listings(new_listings: list[dict]) -> dict:
    store = load_listings()
    for lst in new_listings:
        lid = lst["id"]
        if lid in store:
            store[lid].update(lst)
        else:
            store[lid] = lst
    save_listings(store)
    return store
