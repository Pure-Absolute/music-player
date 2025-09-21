# playlists.py
import os
import json
from utils import safe_write_json

def save_playlist_to(path, queue):
    # queue is list of {"title":..., "url":...}
    if not path.endswith(".json"):
        path = path + ".json"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    safe_write_json(path, queue)
    return path

def load_playlist_from(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []
