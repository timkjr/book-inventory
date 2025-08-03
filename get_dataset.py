#!/usr/bin/env python3
"""Try to download book spine dataset using various methods."""

import requests
import os

def try_direct_download():
    """Try direct download with proper headers"""
    url = "https://universe.roboflow.com/yoloscript/books_spines/dataset/1/download/yolov11"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/zip,application/octet-stream,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    print("Trying direct download with headers...")
    response = requests.get(url, headers=headers, stream=True)
    print(f"Response status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
    print(f"Content-Length: {response.headers.get('content-length', 'Unknown')}")
    
    # Check if we got HTML (sign-in page) or actual zip
    content_start = response.content[:500] if response.content else b""
    if b'<html' in content_start.lower() or b'<!doctype' in content_start.lower():
        print("Got HTML page instead of zip file - authentication required")
        return False
    else:
        print("Got binary content - likely a zip file")
        with open('training/dataset/book_spine_dataset.zip', 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True

def create_simple_dataset():
    """Create a simple dataset structure for testing"""
    print("Creating simple dataset structure for manual annotation...")
    
    os.makedirs('training/dataset/train/images', exist_ok=True)
    os.makedirs('training/dataset/train/labels', exist_ok=True)
    os.makedirs('training/dataset/valid/images', exist_ok=True)
    os.makedirs('training/dataset/valid/labels', exist_ok=True)
    os.makedirs('training/dataset/test/images', exist_ok=True) 
    os.makedirs('training/dataset/test/labels', exist_ok=True)
    
    # Create YAML config file
    yaml_content = """
path: ../dataset  # dataset root dir
train: train/images  # train images (relative to 'path')
val: valid/images    # val images (relative to 'path')
test: test/images    # test images (relative to 'path')

# Classes
names:
  0: book_spine
"""
    
    with open('training/dataset/data.yaml', 'w') as f:
        f.write(yaml_content.strip())
    
    print("Created basic dataset structure.")
    print("You can manually add images and create annotations, or")
    print("we can use a different pre-trained model approach.")
    return True

if __name__ == "__main__":
    os.makedirs('training/dataset', exist_ok=True)
    
    if not try_direct_download():
        create_simple_dataset()