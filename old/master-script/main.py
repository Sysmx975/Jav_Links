import json
import os
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, UTC
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import re
import time

# --- Universal Configuration ---
# This dictionary defines all the scrapers to run.
# You can easily enable/disable scrapers here.
SCRAPER_CONFIG = {
    "missav": {
        "enabled": False,
        "start_url": "https://missav.ws/en/playlists/dprelff6",
        "flaresolverr_url": "http://localhost:8191/v1",
        "max_workers": 11,
    },
    "onejav": {
        "enabled": False,
        "base_url": "https://onejav.com/",
        "days_to_scrape": 30, # Scrape the main page + this many previous days
    },
    "javguru": {
        "enabled": True,
        "base_url": "https://jav.guru/",
        "max_pages_to_scrape": 5,
    }
}

POSTS_FILE = "posts.json"  # The single, unified output file

# --- Data Standardization Function ---
def standardize_post(post_data, source_website):
    """
    Converts a post from any source into a standard format.
    This is the key to making the viewer work with all data.
    """
    # Use UTC for all timestamp operations
    fetch_time = datetime.now(UTC)
    
    # Map raw data to our standard keys
    mapping = {
        "title": post_data.get("title") or post_data.get("text"),
        "page_link": post_data.get("page_link") or post_data.get("link"),
        "cover_image_url": post_data.get("cover_image_url") or post_data.get("image_source"),
        "preview_video_url": post_data.get("preview_video_url"), # Will be None if not present
        "source_website": source_website,
        "original_date": post_data.get("date"), # The original date from the site, if available
        "post_fetched_date": fetch_time.strftime('%Y-%m-%dT%H:%M:%SZ'), # Standard ISO 8601 format
    }
    
    # Ensure page links are absolute URLs
    base_url = SCRAPER_CONFIG.get(source_website.lower(), {}).get('base_url', '')
    if base_url and mapping["page_link"] and not mapping["page_link"].startswith('http'):
        mapping["page_link"] = urljoin(base_url, mapping["page_link"])
        
    if base_url and mapping["cover_image_url"] and not mapping["cover_image_url"].startswith('http'):
        mapping["cover_image_url"] = urljoin(base_url, mapping["cover_image_url"])

    return mapping

# --- Scraper for MissAV (from playlist_index.py) ---
def scrape_missav(config):
    """Scrapes video posts from a MissAV playlist using FlareSolverr."""
    print("\n--- Starting MissAV Scraper ---")
    
    def fetch_single_page(page_url):
        payload = {'cmd': 'request.get', 'url': page_url, 'maxTimeout': 60000}
        try:
            response = requests.post(config["flaresolverr_url"], json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "ok": return []
            
            soup = BeautifulSoup(data["solution"]["response"], 'html.parser')
            posts = []
            for item in soup.find_all('li', class_='sm:flex'):
                title_tag = item.find('label')
                link_tag = item.find('a', href=True)
                img_tag = item.find('img', {'data-src': True})
                video_tag = item.find('video', {'data-src': True})
                if all([title_tag, link_tag, img_tag, video_tag]):
                    posts.append(standardize_post({
                        "title": title_tag.text.strip(),
                        "page_link": link_tag['href'],
                        "cover_image_url": img_tag['data-src'],
                        "preview_video_url": video_tag['data-src'],
                    }, "MissAV"))
            return posts
        except Exception:
            return []

    # Get total pages
    print("-> Discovering total pages...")
    payload = {'cmd': 'request.get', 'url': config["start_url"], 'maxTimeout': 60000}
    try:
        response = requests.post(config["flaresolverr_url"], json=payload, timeout=90).json()
        soup = BeautifulSoup(response["solution"]["response"], 'html.parser')
        pagination_links = soup.select('a[href*="?page="]')
        total_pages = int(pagination_links[-2].text.strip()) if pagination_links else 1
        print(f"-> Found {total_pages} total pages.")
    except Exception as e:
        print(f"[!] Could not determine total pages for MissAV: {e}")
        return []

    # Scrape all pages in parallel
    urls = [f"{config['start_url']}?page={i}" for i in range(1, total_pages + 1)]
    all_posts = []
    with ThreadPoolExecutor(max_workers=config["max_workers"]) as executor:
        future_to_url = {executor.submit(fetch_single_page, url): url for url in urls}
        for future in tqdm(as_completed(future_to_url), total=len(urls), desc="Scraping MissAV"):
            all_posts.extend(future.result())
    
    print(f"--- MissAV Scraper Finished: Found {len(all_posts)} posts ---")
    return all_posts

# --- Scraper for OneJAV (from onejav_index.py) ---
def scrape_onejav(config):
    """Scrapes posts from OneJAV by mimicking 'Load More' API calls."""
    print("\n--- Starting OneJAV Scraper ---")
    all_posts = []
    base_url = config['base_url']
    headers = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}

    def parse_onejav_html(soup):
        found_posts = []
        for container in soup.find_all('div', class_='card-overview'):
            date = container.get('data-date')
            for thumb in container.find_all('div', class_='thumbnail is-inline'):
                link_tag = thumb.find('a', class_='thumbnail-link')
                if link_tag:
                    found_posts.append(standardize_post({
                        'date': date,
                        'link': link_tag.get('href'),
                        'image_source': link_tag.find('img').get('src'),
                        'text': link_tag.find('div', class_='thumbnail-text').get_text(strip=True)
                    }, "OneJAV"))
        return found_posts

    try:
        # Initial page
        print(f"-> Scraping initial page: {base_url}")
        response = requests.get(base_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        all_posts.extend(parse_onejav_html(soup))
        
        if not all_posts: return []
        last_date_str = all_posts[-1]['original_date']
        current_date = datetime.strptime(last_date_str, '%Y-%m-%d')
        
        # Paginated requests
        for _ in tqdm(range(config['days_to_scrape']), desc="Scraping OneJAV"):
            current_date -= timedelta(days=1)
            date_str = current_date.strftime('%Y-%m-%d')
            api_url = f"{base_url}?action=overview&currentdate={date_str}"
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code != 200 or not response.text: break
            
            page_soup = BeautifulSoup(response.text, 'html.parser')
            new_posts = parse_onejav_html(page_soup)
            if not new_posts: break
            all_posts.extend(new_posts)
            time.sleep(0.5) # Be polite

    except Exception as e:
        print(f"[!] An error occurred during OneJAV scraping: {e}")
    
    print(f"--- OneJAV Scraper Finished: Found {len(all_posts)} posts ---")
    return all_posts
    
# --- Scraper for JAVGuru (from javguru_index.py) ---
def scrape_javguru(config):
    """Scrapes posts from JAV.Guru using cloudscraper."""
    print("\n--- Starting JAV.Guru Scraper ---")
    all_posts = []
    base_url = config['base_url']
    scraper = cloudscraper.create_scraper()

    try:
        print("-> Discovering total pages...")
        response = scraper.get(base_url, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        last_page_link = soup.select_one('.wp-pagenavi .last')
        total_pages = 1
        if last_page_link and last_page_link.has_attr('href'):
            match = re.search(r'/page/(\d+)/', last_page_link['href'])
            if match: total_pages = int(match.group(1))
        
        pages_to_scrape = min(config['max_pages_to_scrape'], total_pages)
        print(f"-> Found {total_pages} total pages. Scraping the first {pages_to_scrape}.")
        
        for page_num in tqdm(range(1, pages_to_scrape + 1), desc="Scraping JAV.Guru"):
            page_url = urljoin(base_url, f"page/{page_num}/")
            page_response = scraper.get(page_url, timeout=30)
            page_soup = BeautifulSoup(page_response.content, 'html.parser')

            for article in page_soup.find_all('div', class_='inside-article'):
                link_tag = article.select_one('.imgg a')
                title_tag = article.select_one('.grid1 h2 a')
                date_tag = article.select_one('.date')
                img_tag = article.select_one('.imgg img')

                if not (link_tag and title_tag and date_tag and img_tag): continue
                
                try:
                    date_str = date_tag.get_text(strip=True)
                    parsed_date = datetime.strptime(date_str, '%d %b, %y').strftime('%Y-%m-%d')
                except ValueError:
                    parsed_date = None

                all_posts.append(standardize_post({
                    'date': parsed_date,
                    'link': link_tag.get('href'),
                    'image_source': img_tag.get('src'),
                    'text': title_tag.get('title')
                }, "JAV.Guru"))
            time.sleep(1) # Be polite

    except Exception as e:
        print(f"[!] An unexpected error occurred during JAV.Guru scraping: {e}")

    print(f"--- JAV.Guru Scraper Finished: Found {len(all_posts)} posts ---")
    return all_posts

# --- Main Execution Block ---
def main():
    """Main function to run all enabled scrapers and merge the data."""
    print("--- Starting Master Scraper ---")
    
    # 1. Load existing posts to avoid duplicates
    existing_posts = []
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict) and 'posts' in data:
                    existing_posts = data['posts']
                print(f"-> Loaded {len(existing_posts)} existing posts from '{POSTS_FILE}'.")
            except json.JSONDecodeError:
                print(f"[!] Could not parse '{POSTS_FILE}'. Starting fresh.")
    
    existing_links = {post.get('page_link') for post in existing_posts}

    # 2. Run all enabled scrapers
    all_fetched_posts = []
    if SCRAPER_CONFIG["missav"]["enabled"]:
        all_fetched_posts.extend(scrape_missav(SCRAPER_CONFIG["missav"]))
    if SCRAPER_CONFIG["onejav"]["enabled"]:
        all_fetched_posts.extend(scrape_onejav(SCRAPER_CONFIG["onejav"]))
    if SCRAPER_CONFIG["javguru"]["enabled"]:
        all_fetched_posts.extend(scrape_javguru(SCRAPER_CONFIG["javguru"]))
        
    # 3. Filter out duplicates
    newly_added_posts = [
        post for post in all_fetched_posts if post['page_link'] not in existing_links
    ]
    
    if not newly_added_posts:
        print("\n--- No new posts found across all sources. File is already up-to-date. ---")
        final_posts_list = existing_posts
    else:
        print(f"\n--- Scraping Complete: Found {len(newly_added_posts)} new posts in total. ---")
        final_posts_list = existing_posts + newly_added_posts
    
    # 4. Sort all posts by fetch date (newest first)
    final_posts_list.sort(key=lambda x: x['post_fetched_date'], reverse=True)
    
    # 5. Create the final data structure and save to file
    last_fetched_time = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    final_data = {
        "last_fetched": last_fetched_time,
        "total_videos": len(final_posts_list),
        "posts": final_posts_list
    }

    try:
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        print("-" * 30)
        print("✅ Success! Master file has been updated.")
        print(f"  - File: '{POSTS_FILE}'")
        print(f"  - Last Checked: {last_fetched_time}")
        print(f"  - New Posts Added: {len(newly_added_posts)}")
        print(f"  - Total Posts: {len(final_posts_list)}")
        print("-" * 30)
    except Exception as e:
        print(f"\n[-] Error saving data to JSON file: {e}")

if __name__ == "__main__":
    main()
