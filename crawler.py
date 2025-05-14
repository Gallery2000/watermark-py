import requests
import json
import os
import time
from urllib.parse import urlparse

# Configuration
BASE_URL = "https://testrz.rezhuaclaw.com/adminapi/product/product"
LIMIT_PER_PAGE = 500  # Number of items per page
DOWNLOAD_DIR = "."  # Base directory for downloads (current directory)
SLEEP_BETWEEN_PAGES = 0.5  # Sleep time between page requests to avoid overloading the server
SLEEP_BETWEEN_DOWNLOADS = 0.2  # Sleep time between image downloads

# Create a session for requests
session = requests.Session()

# Add after creating the session
session.headers.update({
    "authori-zation": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwd2QiOiJmNTU1YjJjZmU0MGU0MWNhOTUxMDRmNGY2YzkyOTljMCIsImlzcyI6InRlc3Ryei5yZXpodWFjbGF3LmNvbSIsImF1ZCI6InRlc3Ryei5yZXpodWFjbGF3LmNvbSIsImlhdCI6MTc0NjUzNzkzMSwibmJmIjoxNzQ2NTM3OTMxLCJleHAiOjE3NDkxMjk5MzEsImp0aSI6eyJpZCI6MSwidHlwZSI6ImFkbWluIn19.IliXDx3ekdS4jYWks-QjDiXWTx8k_gOiOxeXHEW9elA",
})

# Global counter for downloaded images
downloaded_count = 0
total_images_found = 0

def get_products_page(page_num):
    """
    Get a single page of products from the API
    """
    params = {
        "page": page_num,
        "limit": LIMIT_PER_PAGE,
        "cate_id": "",
        "type": 1,
        "store_name": "",
        "is_all": ""
    }
    
    try:
        response = session.get(BASE_URL, params=params)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page {page_num}: {e}")
        return None

def extract_image_urls(product):
    """
    Extract all image URLs from a product
    """
    image_urls = []
    
    # Add main image
    if product.get("image") and product["image"].strip():
        image_urls.append(product["image"])
    
    # Add slider images
    if product.get("slider_image") and isinstance(product["slider_image"], list):
        for img in product["slider_image"]:
            if img and img.strip() and img not in image_urls:
                image_urls.append(img)
    
    return image_urls

def download_image(url):
    """
    Download an image from the given URL and save it to the appropriate directory
    """
    global downloaded_count
    
    try:
        # Parse the URL to get the path
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Make sure the URL has a valid path
        if not path or path == "/":
            print(f"Invalid image URL path: {url}")
            return False
        
        # Create the local directory structure based on the URL path
        # Strip the leading slash if present
        path = path.lstrip('/')
        
        # Check if the path is under "attach"
        if not path.startswith("attach/"):
            # If not, we'll put it under attach anyway for consistency
            local_path = os.path.join(DOWNLOAD_DIR, path)
        else:
            local_path = os.path.join(DOWNLOAD_DIR, path)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download the image
        response = session.get(url, stream=True)
        response.raise_for_status()
        
        # Save the image
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Increment counter and display progress
        downloaded_count += 1
        if total_images_found > 0:
            progress_message = f"Downloaded: {downloaded_count}/{total_images_found} images ({downloaded_count/total_images_found*100:.1f}%)"
        else:
            progress_message = f"Downloaded: {downloaded_count} images"
        
        print(f"{progress_message} - {url} -> {local_path}")
        return True
    
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def main():
    global total_images_found
    
    print("Starting image crawler...")
    
    # Get the first page to determine total count
    first_page = get_products_page(1)
    if not first_page or first_page.get("status") != 200:
        print(f"Error accessing API: {first_page.get('msg', 'Unknown error')}")
        return
    
    total_count = first_page["data"]["count"]
    total_pages = (total_count + LIMIT_PER_PAGE - 1) // LIMIT_PER_PAGE
    
    print(f"Found {total_count} products across {total_pages} pages")
    
    # Scan through all pages first to count total images (optional)
    all_image_urls = []
    
    # Add images from first page
    for product in first_page["data"]["list"]:
        all_image_urls.extend(extract_image_urls(product))
    
    # Count images on remaining pages
    for page_num in range(2, total_pages + 1):
        print(f"Scanning page {page_num}/{total_pages} to count images...")
        page_data = get_products_page(page_num)
        if not page_data or page_data.get("status") != 200:
            print(f"Error accessing page {page_num}: {page_data.get('msg', 'Unknown error')}")
            continue
        
        for product in page_data["data"]["list"]:
            all_image_urls.extend(extract_image_urls(product))
    
    # Remove duplicates
    all_image_urls = list(set(all_image_urls))
    total_images_found = len(all_image_urls)
    print(f"Total unique images to download: {total_images_found}")
    
    # Now download all images
    for i, url in enumerate(all_image_urls):
        download_image(url)
        time.sleep(SLEEP_BETWEEN_DOWNLOADS)
    
    print(f"Image crawling completed! Downloaded {downloaded_count} out of {total_images_found} images.")

if __name__ == "__main__":
    main()
