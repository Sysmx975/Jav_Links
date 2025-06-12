import sys
import cloudscraper
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time

def unpack_js_packer(packed_js):
    """
    A pure Python implementation to unpack the popular 'eval(function(p,a,c,k,e,d)...)' JS packer.
    
    Args:
        packed_js (str): The entire packed JavaScript string.

    Returns:
        str: The deobfuscated (unpacked) JavaScript code or None if it fails.
    """
    try:
        # This regex is the key to extracting the packer's arguments
        match = re.search(r"}\('(.+)',(\d+),(\d+),'(.+?)'\.split\('\|'\)", packed_js)
        if not match:
            return None

        payload, radix, count, symbols = match.groups()
        radix = int(radix)
        count = int(count)
        symbols = symbols.split('|')

        # This function converts an integer to a base-n string, crucial for the symbol table
        def int_to_base_n(num, base):
            if num < 0: return ''
            if num == 0: return '0'
            alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
            if num < base:
                return alphabet[num]
            else:
                return int_to_base_n(num // base, base) + alphabet[num % base]

        # Create a dictionary for fast symbol lookups
        symbol_table = {int_to_base_n(i, radix): sym for i, sym in enumerate(symbols)}

        # Use a regex to perform the replacements
        # This finds all the alphanumeric "words" to be replaced
        return re.sub(r'\b(\w+)\b', lambda m: symbol_table.get(m.group(1), m.group(1)), payload)

    except Exception as e:
        print(f"    [!] Warning: Failed to unpack a JS block. Error: {e}")
        return None

def find_m3u8_in_url(url, scraper_session):
    """
    Finds M3U8 resources from a single URL.

    Args:
        url (str): The URL to scrape.
        scraper_session: An active cloudscraper session object.

    Returns:
        set: A set of M3U8 URLs found on the page.
    """
    found_m3u8 = set()
    try:
        print(f"[*] Processing URL: {url}")
        response = scraper_session.get(url, timeout=30)
        response.raise_for_status()

        page_content = response.text
        soup = BeautifulSoup(page_content, 'html.parser')

        # --- 1. Find M3U8 Links using advanced de-obfuscation ---
        print("    [*] Searching for obfuscated JavaScript resources...")
        for script in soup.find_all("script", string=re.compile(r"eval\(function\(p,a,c,k,e,d\)")):
            unpacked_code = unpack_js_packer(script.string)
            if unpacked_code:
                m3u8_pattern = re.compile(r'https?://[^\s"\'`]+\.m3u8[^\s"\'`]*')
                urls = m3u8_pattern.findall(unpacked_code)
                for u in urls:
                    found_m3u8.add(u)

        # --- 2. Find standard M3U8 Links (fallback) ---
        print("    [*] Searching for standard M3U8 links...")
        m3u8_pattern_fallback = re.compile(r'https?://[^\s"\'`]+\.m3u8[^\s"\'`]*')
        urls_fallback = m3u8_pattern_fallback.findall(page_content)
        for u in urls_fallback:
            found_m3u8.add(u)

        if found_m3u8:
             print(f"    [+] Found {len(found_m3u8)} M3U8 link(s) for this URL.")
        else:
             print("    [-] No M3U8 links found for this URL.")
        
        return found_m3u8

    except Exception as e:
        print(f"    [!] An error occurred while processing {url}: {e}")
        return found_m3u8 # Return any links found before the error

def main(input_file, output_file):
    """
    Main function to read URLs from a file, find M3U8 links, and save them.
    """
    try:
        with open(input_file, 'r') as f:
            urls_to_process = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[!] Error: Input file '{input_file}' not found.")
        sys.exit(1)

    if not urls_to_process:
        print(f"[!] Input file '{input_file}' is empty.")
        sys.exit(1)

    all_found_links = set()
    scraper = cloudscraper.create_scraper() # Create one session to reuse

    print(f"[*] Found {len(urls_to_process)} URLs to process from '{input_file}'.")
    
    for url in urls_to_process:
        links = find_m3u8_in_url(url, scraper)
        all_found_links.update(links)
        time.sleep(1) # Be a polite scraper

    if all_found_links:
        print(f"\n[*] Writing {len(all_found_links)} unique M3U8 links to '{output_file}'...")
        with open(output_file, 'w') as f:
            for link in sorted(list(all_found_links)):
                if "playlist" in link:
                    f.write(link + '\n')
        print("[*] Done.")
    else:
        print("\n[*] No M3U8 links were found across all provided URLs.")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python resource_finder.py <path_to_links.txt>")
        sys.exit(1)
    
    input_filename = sys.argv[1]
    output_filename = 'output.txt'
    main(input_filename, output_filename)
