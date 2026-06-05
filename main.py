from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
import re
import logging
from pathlib import Path
from tmdb import search_tmdb, parse_name, TMDB_API_KEY, BASE_URL
import requests

# --- Logging Setup ---
if os.path.exists("app.log"):
    os.remove("app.log")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler("app.log"), logging.StreamHandler()])
logger = logging.getLogger("renamer")

app = FastAPI(title="Jellyfin Renamer UI")

# --- Models ---
class MediaItem(BaseModel):
    id: str
    current_name: str
    proposed_name: Optional[str] = None
    media_type: str
    tmdb_id: Optional[int] = None
    year: Optional[str] = None
    path: str
    status: str = "pending" # pending, matching, matched, failed

class RenameRequest(BaseModel):
    items: List[MediaItem]

class OverrideRequest(BaseModel):
    path: str
    tmdb_id: int
    media_type: str

@app.get("/api/logs")
async def get_logs():
    try:
        if os.path.exists("app.log"):
            with open("app.log", "r") as f: return {"logs": f.readlines()[-100:]}
        return {"logs": ["Log file not found."]}
    except: return {"logs": []}

@app.get("/api/scan")
async def scan_folders():
    """Step 1: Scan filesystem for Movies and TV Shows."""
    movie_dir = os.getenv("MOVIE_DIR", "test_media/movies")
    tv_dir = os.getenv("TV_DIR", "test_media/tv")
    results = []
    
    # Process Movies (assuming flat structure)
    path_m = Path(movie_dir)
    if path_m.exists():
        for item in path_m.iterdir():
            if item.is_dir() and "[tmdbid-" not in item.name:
                results.append(MediaItem(id=str(item.absolute()), current_name=item.name, media_type="movie", path=str(item.absolute()), status="pending"))
    
    # Process TV Shows (Show -> Season folders)
    path_t = Path(tv_dir)
    if path_t.exists():
        for show_folder in path_t.iterdir():
            if show_folder.is_dir() and "[tmdbid-" not in show_folder.name:
                # Check if it has season folders
                seasons = [s for s in show_folder.iterdir() if s.is_dir() and "season" in s.name.lower()]
                if seasons:
                    # Treat the show folder itself as the item to rename
                    results.append(MediaItem(id=str(show_folder.absolute()), current_name=show_folder.name, media_type="tv", path=str(show_folder.absolute()), status="pending"))
                else:
                    # Flat TV show structure
                    results.append(MediaItem(id=str(show_folder.absolute()), current_name=show_folder.name, media_type="tv", path=str(show_folder.absolute()), status="pending"))
    return results

@app.post("/api/match")
async def match_item(item: MediaItem):
    """Step 2: Match item against TMDB."""
    title, year = parse_name(item.current_name)
    logger.info(f"Matching: {item.current_name} -> {title}")
    
    try:
        data = search_tmdb(title, year, item.media_type)
        if data:
            return create_media_item_from_data(item, data)
        item.status = "failed"
        return item
    except Exception as e:
        logger.error(f"Error matching {item.current_name}: {e}")
        item.status = "failed"
        return item

@app.post("/api/override")
async def override_tmdb_id(request: OverrideRequest):
    url = f"{BASE_URL}/{request.media_type}/{request.tmdb_id}"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    if response.status_code != 200: raise HTTPException(status_code=400, detail="Invalid ID")
    return create_media_item_from_data(MediaItem(id=request.path, current_name=Path(request.path).name, media_type=request.media_type, path=request.path), response.json())

def has_season_marker(name: str) -> bool:
    return bool(re.search(r'(?i)\bSeason\s*\d+\b|\bS\d{1,2}\b', name))


def create_media_item_from_data(item, tmdb_data):
    title = tmdb_data.get("title") or tmdb_data.get("name")
    year = (tmdb_data.get("release_date") or tmdb_data.get("first_air_date") or "")[:4]
    tmdb_id = tmdb_data["id"]
    new_name = re.sub(r'[\\/*?:"<>|]', "", f"{title} ({year}) [tmdbid-{tmdb_id}]")
    item.proposed_name = new_name

    if item.media_type == "tv" and has_season_marker(item.current_name):
        item.proposed_name = f"{new_name}/{item.current_name}"

    item.tmdb_id = tmdb_id
    item.year = year
    item.status = "matched"
    return item

import json

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_to_history(items):
    history = load_history()
    history.extend([item.dict() for item in items])
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

@app.get("/api/history")
async def get_history():
    return {"items": load_history()}

@app.post("/api/rename")
async def rename_items(request: RenameRequest):
    renamed = []
    for item in request.items:
        old = Path(item.path)
        if old.exists() and item.proposed_name:
            try:
                new_path = old.parent / item.proposed_name
                new_path.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new_path)
                renamed.append(item)
            except Exception as e:
                logger.error(f"Failed to rename {old}: {e}")
    if renamed:
        save_to_history(renamed)
    return {"status": "success", "count": len(renamed)}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
