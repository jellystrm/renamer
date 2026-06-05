import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

def search_tmdb(query, year=None, media_type="movie"):
    """Search TMDB for a movie or TV show."""
    if not TMDB_API_KEY:
        raise Exception("TMDB_API_KEY is not configured. Set TMDB_API_KEY in your .env or environment variables.")
    
    endpoint = f"{BASE_URL}/search/{media_type}"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
    }
    
    # TV shows use first_air_date_year instead of year in search
    if year:
        if media_type == "movie":
            params["year"] = year
        else:
            params["first_air_date_year"] = year

    response = requests.get(endpoint, params=params)
    
    # Handle API errors (e.g., 401 Unauthorized)
    if response.status_code == 401:
        raise Exception(f"TMDB API Key is invalid (Status 401). Check your .env file.")
    
    response.raise_for_status()
    
    results = response.json().get("results", [])
    if not results:
        return None # Explicitly return None for "No match found"
        
    # Sort by popularity to get the most likely match
    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return results[0]
def strip_season_information(name):
    """Remove season-specific labels like 'Season 1' or 'S01' from a title."""
    name = re.sub(r'(?i)\bSeason\s*\d+\b', '', name)
    name = re.sub(r'(?i)\bSeries\s*\d+\b', '', name)
    name = re.sub(r'(?i)\bS\d{1,2}(?:E\d{1,2})?\b', '', name)
    return name


def parse_name(folder_name):
    """Extract title and year from folder name."""
    # Look for year (19xx or 20xx) preceded by non-alphanumeric or start of string
    # and followed by non-alphanumeric or end of string
    year_match = re.search(r'(?:^|[\.\s\-\_\(\[])(19\d{2}|20\d{2})(?:[\.\s\-\_\)\]]|$)', folder_name)
    year = year_match.group(1) if year_match else None

    # Replace common separators with spaces
    clean_title = re.sub(r'[\.\-\_]', ' ', folder_name)
    clean_title = strip_season_information(clean_title)

    if year:
        # Split by year to get the title part
        clean_title = clean_title.split(year)[0]

    # Clean title: Remove common quality tags
    clean_title = re.sub(r'(1080p|720p|2160p|4k|bluray|web-dl|h264|h265|x264|x265|multi|vostfr|sub|remux|s\d{1,2}e\d{1,2}).*', '', clean_title, flags=re.IGNORECASE).strip()

    # Remove leading/trailing spaces and multiple spaces
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()

    return clean_title, year
