import requests
from bs4 import BeautifulSoup
import json
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
FLARESOLVERR_URL = "http://localhost:8191/v1"
START_URL = "https://missav.ws/en/playlists/dprelff6"
OUTPUT_FILE = "posts.json"
MAX_WORKERS = 11 # Number of parallel threads. Adjust based on your machine's and FlareSolverr's capacity.

def get_total_pages(start_url):
    """
    Fetches the first page to determine the total number of pages in the playlist.
    """
    print(f"-> Discovering total number of pages from: {start_url}")
    payload = {'cmd': 'request.get', 'url': start_url, 'maxTimeout': 60000}
    
    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            print(f"[!] FlareSolverr failed during page discovery: {data.get('message')}")
            return None

        soup = BeautifulSoup(data["solution"]["response"], 'html.parser')
        
        # Find all pagination links and get the last one to determine the total page count
        pagination_links = soup.select('a[href*="?page="]')
        if not pagination_links:
            # If no pagination links, assume there's only one page
            return 1
            
        last_page_link = pagination_links[-2] # The last number before the 'Next' arrow
        total_pages = int(last_page_link.text.strip())
        
        print(f"-> Found {total_pages} total pages.")
        return total_pages
        
    except Exception as e:
        print(f"[!] Could not determine total pages: {e}")
        return None

def fetch_single_page_posts(page_url):
    """
    Fetches a single page and extracts all post data from it.
    This function is designed to be run in a parallel thread.
    """
    payload = {'cmd': 'request.get', 'url': page_url, 'maxTimeout': 60000}
    
    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            return [] # Fail silently for a single page to not stop the whole batch

        soup = BeautifulSoup(data["solution"]["response"], 'html.parser')
        posts = []
        for post_item in soup.find_all('li', class_='sm:flex'):
            title_tag = post_item.find('label')
            link_tag = post_item.find('a', href=True)
            img_tag = post_item.find('img', {'data-src': True})
            video_tag = post_item.find('video', {'data-src': True})

            if all([title_tag, link_tag, img_tag, video_tag]):
                posts.append({
                    "title": title_tag.text.strip(),
                    "page_link": link_tag['href'],
                    "cover_image_url": img_tag['data-src'],
                    "preview_video_url": video_tag['data-src'],
                })
        return posts
        
    except Exception:
        return [] # Fail silently

# --- Main execution block ---
if __name__ == "__main__":
    print("--- Starting Parallel Playlist Scraper ---")
    
    # STAGE 1: Discover all page URLs
    total_pages = get_total_pages(START_URL)
    
    if not total_pages:
        print("[-] Could not start scraping. Exiting.")
    else:
        all_page_urls = [f"{START_URL}?page={i}" for i in range(1, total_pages + 1)]
        all_posts_data = []

        # STAGE 2: Fetch all pages in parallel
        print(f"\nFetching {len(all_page_urls)} pages using {MAX_WORKERS} parallel workers...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all pages to the executor
            future_to_url = {executor.submit(fetch_single_page_posts, url): url for url in all_page_urls}
            
            # Process results as they complete, with a progress bar
            for future in tqdm(as_completed(future_to_url), total=len(all_page_urls), desc="Processing Pages"):
                posts_from_page = future.result()
                if posts_from_page:
                    all_posts_data.extend(posts_from_page)
        
        # STAGE 3: Save the final results
        if all_posts_data:
            print(f"\n--- Scraping Complete ---")
            print(f"Found a total of {len(all_posts_data)} posts.")
            
            try:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_posts_data, f, ensure_ascii=False, indent=4)
                print(f"[+] All data successfully saved to '{OUTPUT_FILE}'")
            except Exception as e:
                print(f"\n[-] Error saving data to JSON file: {e}")
        else:
            print("\n--- No posts were found across any page. ---")