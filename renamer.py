import os
import re
import requests
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
MOVIE_DIR = os.getenv("MOVIE_DIR", "/movies")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"

def get_movie_info(title, year=None):
    """Fetch movie info from TMDB."""
    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
    }
    if year:
        params["year"] = year
    
    try:
        response = requests.get(TMDB_SEARCH_URL, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
        if results:
            return results[0]  # Return the best match
    except Exception as e:
        print(f"Error searching TMDB for {title}: {e}")
    return None

def parse_filename(name):
    """Extract title and year from filename."""
    # Pattern to find a year like (1990) or 1990
    year_match = re.search(r'[\(\s](19\d{2}|20\d{2})[\)\s]', name)
    year = year_match.group(1) if year_match else None
    
    # Clean title: remove everything after the year or common quality tags
    clean_title = name
    if year:
        clean_title = name.split(year)[0]
    
    # Further cleaning
    clean_title = re.sub(r'[\.\-\_]', ' ', clean_title).strip()
    clean_title = re.sub(r'\s+', ' ', clean_title)
    
    return clean_title, year

def rename_item(item_path):
    """Rename a file or directory."""
    name = item_path.name
    if item_path.is_file():
        stem = item_path.stem
        extension = item_path.suffix
    else:
        stem = name
        extension = ""

    # Skip if already has an identifier
    if "[tmdbid-" in name or "[imdbid-" in name:
        print(f"Skipping (already identified): {name}")
        return

    title, year = parse_filename(stem)
    print(f"Searching: '{title}'" + (f" ({year})" if year else ""))
    
    movie_data = get_movie_info(title, year)
    
    if movie_data:
        tmdb_id = movie_data['id']
        official_title = movie_data['title']
        release_year = movie_data['release_date'][:4] if movie_data.get('release_date') else year
        
        # Jellyfin standard: Name (Year) [tmdbid-ID]
        new_name = f"{official_title} ({release_year}) [tmdbid-{tmdb_id}]{extension}"
        # Remove characters illegal in filesystems
        new_name = re.sub(r'[\\/*?:"<>|]', "", new_name)
        
        new_path = item_path.parent / new_name
        
        if name == new_name:
            print(f"Already matches standard: {name}")
            return

        if DRY_RUN:
            print(f"[DRY RUN] Would rename: '{name}' -> '{new_name}'")
        else:
            try:
                item_path.rename(new_path)
                print(f"Renamed: '{name}' -> '{new_name}'")
            except Exception as e:
                print(f"Failed to rename {name}: {e}")
    else:
        print(f"No match found for: {title}")

def main():
    if not TMDB_API_KEY:
        print("Error: TMDB_API_KEY is not set in environment.")
        return

    path = Path(MOVIE_DIR)
    if not path.exists():
        print(f"Error: Path {MOVIE_DIR} does not exist.")
        return

    print(f"Starting scan in: {MOVIE_DIR} (Dry Run: {DRY_RUN})")
    
    # Process immediate subdirectories (folders) or files in root
    for item in path.iterdir():
        if item.is_dir() or (item.is_file() and item.suffix.lower() in ['.mkv', '.mp4', '.avi', '.mov']):
            rename_item(item)

if __name__ == "__main__":
    main()
