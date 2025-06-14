import cloudscraper
from bs4 import BeautifulSoup
import json
from datetime import datetime, UTC
import time
import re
from urllib.parse import urljoin
import os
from tqdm import tqdm

# --- Configuration ---
BASE_URL = "https://jav.guru/"
POSTS_FILE = "data/javguru.json"
MAX_PAGES_TO_SCRAPE = 15

def load_existing_links(filename):
    """Loads existing post links to avoid re-scraping."""
    if not os.path.exists(filename):
        return set()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'posts' in data:
            links = {post.get('link') for post in data['posts']}
            print(f"-> Found {len(links)} existing posts in '{filename}'.")
            return links
    except (json.JSONDecodeError, KeyError):
        return set()
    return set()

def scrape_jav_guru(base_url, max_pages, scraper):
    """
    Scrapes posts directly from JAV.Guru listing pages,
    using the corrected logic to find cover images.
    """
    all_posts = []
    print("-> Discovering total pages for JAV.Guru...")
    try:
        response = scraper.get(base_url, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        last_page_link = soup.select_one('.wp-pagenavi .last')
        total_pages = 1
        if last_page_link and last_page_link.has_attr('href'):
            match = re.search(r'/page/(\d+)/', last_page_link['href'])
            if match: total_pages = int(match.group(1))
        
        pages_to_scrape = min(max_pages, total_pages)
        print(f"-> Found {total_pages} total pages. Scraping the first {pages_to_scrape}.")

        post_fetch_time = datetime.now(UTC).isoformat()
        
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
                
                # --- THIS IS THE CORRECTED LOGIC FROM THE MASTER SCRIPT ---
                # It prioritizes 'data-src' for lazy-loaded images, then falls back to 'src'.
                image_url = img_tag.get('data-src') or img_tag.get('src')
                # --- END CORRECTION ---

                try:
                    parsed_date = datetime.strptime(date_tag.get_text(strip=True), '%d %b, %y').strftime('%Y-%m-%d')
                except ValueError:
                    parsed_date = None

                all_posts.append({
                    'date': parsed_date,
                    'link': urljoin(base_url, link_tag.get('href')),
                    'image_source': urljoin(base_url, image_url) if image_url else None,
                    'text': title_tag.get('title'),
                    'post_fetched_date': post_fetch_time
                })
            time.sleep(1) # Be polite
        
        return all_posts

    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        return []

if __name__ == '__main__':
    print(f"--- Running JAV.Guru Scraper ---")
    scraper = cloudscraper.create_scraper()

    # Load links of posts we already have
    existing_links = load_existing_links(POSTS_FILE)
    
    # Scrape the listing pages
    scraped_posts = scrape_jav_guru(BASE_URL, MAX_PAGES_TO_SCRAPE, scraper)
    
    # Filter out posts we already have in our JSON file
    newly_added = [p for p in scraped_posts if p['link'] not in existing_links]
    print(f"\n-> Found {len(newly_added)} new posts from JAV.Guru.")

    if newly_added:
        # Load old posts from the file to append to them
        if os.path.exists(POSTS_FILE):
            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                try:
                    final_posts_list = json.load(f).get('posts', []) + newly_added
                except (json.JSONDecodeError, AttributeError):
                    final_posts_list = newly_added
        else:
            final_posts_list = newly_added
        
        # Sort the combined list by date
        final_posts_list.sort(key=lambda x: x.get('date') or '1970-01-01', reverse=True)

        final_data = {
            "last_fetched": datetime.now(UTC).isoformat(),
            "source_website": "JAV.Guru",
            "total_videos": len(final_posts_list),
            "posts": final_posts_list
        }
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        print(f"✅ Success! '{POSTS_FILE}' updated. Total posts: {len(final_posts_list)}.")
    else:
        print("\n--- No new posts found. The file is already up-to-date. ---")
