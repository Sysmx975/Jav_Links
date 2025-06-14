import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import time
import os
import concurrent.futures
from tqdm import tqdm

def fetch_page_with_flaresolverr(flaresolverr_url: str, target_url: str) -> str | None:
    """
    Fetches a webpage using FlareSolverr to bypass Cloudflare.

    Args:
        flaresolverr_url (str): The URL of your running FlareSolverr instance.
        target_url (str): The URL of the website you want to fetch.

    Returns:
        str | None: The HTML content of the page if successful, None otherwise.
    """
    payload = {
        "cmd": "request.get",
        "url": target_url,
        "maxTimeout": 60000,
    }
    # This function is not suitable for a progress bar, so verbose output is kept.
    # print(f"Sending request to FlareSolverr for URL: {target_url}")
    try:
        response = requests.post(
            f"{flaresolverr_url}/v1",
            json=payload,
            timeout=70
        )
        response.raise_for_status()
        result = response.json()
        if result and result.get("status") == "ok" and result.get("solution"):
            # print(f"Successfully fetched {target_url}")
            return result["solution"]["response"]
        else:
            # print(f"FlareSolverr request failed for {target_url}: {result.get('message', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        # print(f"An error occurred during the request to FlareSolverr for {target_url}: {e}")
        return None
    except json.JSONDecodeError:
        # print(f"Failed to decode JSON response from FlareSolverr for {target_url}.")
        return None

def extract_posts_from_html(html_content: str, base_url: str) -> list[dict]:
    """
    Extracts post details from the given HTML content.

    Args:
        html_content (str): The HTML content of the webpage.
        base_url (str): The base URL of the website to resolve relative URLs.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a post.
    """
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    posts_data = []
    movie_list = soup.find('ul', class_='MovieList')
    if not movie_list:
        return []
    posts = movie_list.find_all('li', class_='TPostMv')
    for post in posts:
        main_link_tag = post.find('a')
        post_url = main_link_tag.get('href') if main_link_tag else 'N/A'
        if post_url and not post_url.startswith(('http://', 'https://')):
            post_url = urljoin(base_url, post_url)
        title_tag = post.find('h2', class_='Title')
        title = title_tag.text.strip() if title_tag else 'N/A'
        img_tag = post.find('img')
        image_url = img_tag.get('src') if img_tag else 'N/A'
        views_tag = post.find('span', class_='Views')
        views = views_tag.text.strip() if views_tag else 'N/A'
        genre_tags = post.select('.Description .Genre a')
        genres = [tag.text.strip() for tag in genre_tags] if genre_tags else []
        posts_data.append({
            'title': title,
            'url': post_url,
            'image_url': image_url,
            'views': views,
            'genres': genres
        })
    return posts_data

def get_direct_video_link(post_url: str) -> str | None:
    """
    Uses an external API to get the direct video link for a given post URL.

    Args:
        post_url (str): The URL of the post page.

    Returns:
        str | None: The direct video link if found, otherwise None.
    """
    if not post_url or post_url == 'N/A':
        return None
    
    api_url = f"https://fetch.mrspidyxd.workers.dev/?url={post_url}&extract=true"
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            extracted_urls = data.get("extractedUrls", {})
            other_media = extracted_urls.get("otherMedia", [])
            if other_media:
                return other_media[0]
        return None
    except requests.exceptions.RequestException:
        # Errors will be common in concurrent requests, so we suppress verbose logging.
        return None
    except json.JSONDecodeError:
        return None

def save_data_to_json(data: list, filename: str):
    """
    Saves the provided data to a JSON file.

    Args:
        data (list): The list of dictionaries to save.
        filename (str): The name of the file to save the data to.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully saved all data to '{filename}'")
        print(f"File saved at: {os.path.abspath(filename)}")
    except IOError as e:
        print(f"Error saving data to file: {e}")

if __name__ == "__main__":
    # --- Configuration ---
    FLARESOLVERR_URL = "http://localhost:8191"
    BASE_WEBSITE_URL = "https://hanimes.org/tag/hanime/"
    OUTPUT_JSON_FILE = "hanime.json"
    MAX_WORKERS = 11 # Number of concurrent threads for fetching video links

    print(f"Starting scraper for: {BASE_WEBSITE_URL}")
    print(f"Using FlareSolverr instance at: {FLARESOLVERR_URL}")

    all_posts_data = []
    page_number = 1
    
    # --- Main Scraping Loop ---
    with tqdm(desc="Scraping Pages", unit="page") as pbar_pages:
        while True:
            target_page_url = f"{BASE_WEBSITE_URL}page/{page_number}/" if page_number > 1 else BASE_WEBSITE_URL
            pbar_pages.set_description(f"Scraping Page {page_number}")
            
            page_html = fetch_page_with_flaresolverr(FLARESOLVERR_URL, target_page_url)
            
            if not page_html:
                print("\nFailed to fetch page HTML. Stopping pagination.")
                break
                
            posts_on_page = extract_posts_from_html(page_html, BASE_WEBSITE_URL)
            
            if not posts_on_page:
                print("\nNo more posts found. Reached the end.")
                break
                
            # Use ThreadPoolExecutor to fetch direct links concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Create a mapping from future to post to update it later
                future_to_post = {executor.submit(get_direct_video_link, post['url']): post for post in posts_on_page}
                
                # Process completed futures with a progress bar
                for future in tqdm(concurrent.futures.as_completed(future_to_post), total=len(posts_on_page), desc=f"Fetching links for page {page_number}"):
                    post = future_to_post[future]
                    try:
                        direct_link = future.result()
                        post['direct_video_link'] = direct_link if direct_link else 'N/A'
                    except Exception as exc:
                        post['direct_video_link'] = 'Error'
                        # print(f"{post['title']} generated an exception: {exc}")

            all_posts_data.extend(posts_on_page)
            page_number += 1
            pbar_pages.update(1)
        
    # --- Save Results ---
    if all_posts_data:
        save_data_to_json(all_posts_data, OUTPUT_JSON_FILE)
    else:
        print("\nNo posts were scraped. The output file will not be created.")

    print("\nScript finished.")
