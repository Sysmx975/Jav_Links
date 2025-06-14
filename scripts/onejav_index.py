import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, UTC
import time
import os
from urllib.parse import urljoin # <-- FIXED: Added this import for building URLs
from tqdm import tqdm # <-- FIXED: Added this import for the progress bar

# --- Configuration ---
BASE_URL = "https://onejav.com/"
POSTS_FILE = "data/onejav.json" # Output file for this script
DAYS_TO_SCRAPE = 30

def parse_posts_from_html(soup, base_url, fetch_time):
    posts = []
    for container in soup.find_all('div', class_='card-overview'):
        date = container.get('data-date')
        for thumbnail in container.find_all('div', class_='thumbnail is-inline'):
            link_tag = thumbnail.find('a', class_='thumbnail-link')
            if link_tag:
                link = link_tag.get('href')
                if link and not link.startswith('http'):
                   link = urljoin(base_url, link)

                posts.append({
                    'date': date,
                    'link': link,
                    'image_source': link_tag.find('img').get('src'),
                    'text': link_tag.find('div', class_='thumbnail-text').get_text(strip=True),
                    'post_fetched_date': fetch_time # Standardized date field
                })
    return posts

def scrape_all_posts(base_url, days_to_scrape):
    all_posts = []
    headers = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}
    fetch_time = datetime.now(UTC).isoformat()

    try:
        print(f"-> Scraping initial page: {base_url}")
        response = requests.get(base_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_posts.extend(parse_posts_from_html(soup, base_url, fetch_time))
        if not all_posts: return []
            
        last_date_str = all_posts[-1]['date']
        current_date = datetime.strptime(last_date_str, '%Y-%m-%d')
        
        for _ in tqdm(range(days_to_scrape), desc="Scraping OneJAV"):
            current_date -= timedelta(days=1)
            date_str = current_date.strftime('%Y-%m-%d')
            api_url = f"{base_url}?action=overview&currentdate={date_str}"
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code != 200 or not response.text: break
            
            page_soup = BeautifulSoup(response.text, 'html.parser')
            new_posts = parse_posts_from_html(page_soup, base_url, fetch_time)
            if not new_posts: break
            all_posts.extend(new_posts)
            time.sleep(0.5)

        return all_posts
    except Exception as e:
        print(f"[!] An error occurred during OneJAV scraping: {e}")
        return []

if __name__ == '__main__':
    print(f"--- Running OneJAV Scraper ---")
    scraped_posts = scrape_all_posts(BASE_URL, DAYS_TO_SCRAPE)

    # Use a set of links for efficient duplicate checking
    unique_posts_map = {p['link']: p for p in scraped_posts}
    
    # Load existing posts to update the file correctly
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                if isinstance(existing_data, dict) and 'posts' in existing_data:
                    existing_posts = existing_data.get('posts', [])
                    for p in existing_posts:
                        # Add existing posts to the map, only if not already scraped
                        if p['link'] not in unique_posts_map:
                             unique_posts_map[p['link']] = p
            except (json.JSONDecodeError, AttributeError):
                pass
                
    final_posts_list = list(unique_posts_map.values())
    final_posts_list.sort(key=lambda x: x['post_fetched_date'], reverse=True)
    
    print(f"\n-> Found {len(scraped_posts)} posts this run. Total unique posts are {len(final_posts_list)}.")

    final_data = {
        "last_fetched": datetime.now(UTC).isoformat(),
        "source_website": "OneJAV",
        "total_videos": len(final_posts_list),
        "posts": final_posts_list
    }
    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    print(f"✅ Success! '{POSTS_FILE}' updated with {len(final_posts_list)} total posts.")
