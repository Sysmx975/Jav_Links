import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, UTC
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
FLARESOLVERR_URL = "http://localhost:8191/v1"
START_URL = "https://missav.ws/en/playlists/dprelff6"
POSTS_FILE = "docs/data/playlist.json"  # Output file for this script
MAX_WORKERS = 11

def load_existing_posts(filename):
    if not os.path.exists(filename):
        return [], set()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'posts' in data:
            posts = data.get('posts', [])
            links = {post.get('page_link') for post in posts}
            print(f"-> Found {len(posts)} existing posts in '{filename}'.")
            return posts, links
    except (json.JSONDecodeError, KeyError):
        print(f"[!] Error reading '{filename}'. Starting fresh.")
    return [], set()

def get_total_pages(start_url):
    print("-> Discovering total pages for MissAV...")
    payload = {'cmd': 'request.get', 'url': start_url, 'maxTimeout': 60000}
    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=90).json()
        soup = BeautifulSoup(response["solution"]["response"], 'html.parser')
        pagination_links = soup.select('a[href*="?page="]')
        total_pages = int(pagination_links[-2].text.strip()) if pagination_links else 1
        print(f"-> Found {total_pages} total pages.")
        return total_pages
    except Exception as e:
        print(f"[!] Could not determine total pages: {e}")
        return None

def fetch_single_page_posts(page_url):
    payload = {'cmd': 'request.get', 'url': page_url, 'maxTimeout': 60000}
    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=90).json()
        if response.get("status") != "ok": return []
        
        soup = BeautifulSoup(response["solution"]["response"], 'html.parser')
        posts = []
        # The fetch time is now recorded for each post
        post_fetch_time = datetime.now(UTC).isoformat()
        
        for item in soup.find_all('li', class_='sm:flex'):
            title_tag = item.find('label')
            link_tag = item.find('a', href=True)
            img_tag = item.find('img', {'data-src': True})
            video_tag = item.find('video', {'data-src': True})
            if all([title_tag, link_tag, img_tag, video_tag]):
                posts.append({
                    "title": title_tag.text.strip(),
                    "page_link": link_tag['href'],
                    "cover_image_url": img_tag['data-src'],
                    "preview_video_url": video_tag['data-src'],
                    "post_fetched_date": post_fetch_time, # Standardized date field
                })
        return posts
    except Exception:
        return []

if __name__ == "__main__":
    print(f"--- Running MissAV Playlist Scraper ---")
    existing_posts, existing_links = load_existing_posts(POSTS_FILE)
    total_pages = get_total_pages(START_URL)
    
    if total_pages:
        all_urls = [f"{START_URL}?page={i}" for i in range(1, total_pages + 1)]
        all_fetched_posts = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_single_page_posts, url): url for url in all_urls}
            for future in tqdm(as_completed(future_to_url), total=len(all_urls), desc="Scraping MissAV"):
                all_fetched_posts.extend(future.result())
        
        newly_added = [p for p in all_fetched_posts if p['page_link'] not in existing_links]
        print(f"\n-> Found {len(newly_added)} new posts from MissAV.")
        
        final_posts_list = existing_posts + newly_added
        # Sort by the fetched date, newest first
        final_posts_list.sort(key=lambda x: x['post_fetched_date'], reverse=True)

        final_data = {
            "last_fetched": datetime.now(UTC).isoformat(),
            "source_website": "MissAV",
            "total_videos": len(final_posts_list),
            "posts": final_posts_list
        }
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        print(f"✅ Success! '{POSTS_FILE}' updated with {len(final_posts_list)} total posts.")

