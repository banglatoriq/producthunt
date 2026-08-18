"""
store.py — সেভ করা প্রোডাক্টগুলো লোকাল JSON ফাইলে রাখা।

ডেটাবেস লাগে না। data/products.json ফাইলেই সব থাকে, তাই অ্যাপ রিস্টার্ট
করলেও ডেটা থাকে। ব্যাকআপ = শুধু ওই ফাইলটা কপি করা।
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "products.json")


def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_all() -> List[Dict]:
    _ensure()
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_all(rows: List[Dict]):
    _ensure()
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)   # atomic — অর্ধেক লেখা ফাইল থাকবে না


def add_product(record: Dict) -> str:
    rows = load_all()
    record = dict(record)
    record["id"] = str(uuid.uuid4())[:8]
    record["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows.append(record)
    save_all(rows)
    return record["id"]


def update_product(pid: str, patch: Dict) -> bool:
    rows = load_all()
    for row in rows:
        if row.get("id") == pid:
            row.update(patch)
            save_all(rows)
            return True
    return False


def delete_product(pid: str) -> bool:
    rows = load_all()
    new = [r for r in rows if r.get("id") != pid]
    if len(new) == len(rows):
        return False
    save_all(new)
    return True


def get_product(pid: str):
    for row in load_all():
        if row.get("id") == pid:
            return row
    return None
