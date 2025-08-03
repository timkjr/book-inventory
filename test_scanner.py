#!/usr/bin/env python3
"""
Test script to trigger the scanner and examine segmented outputs
"""

import requests
import os
import time

def test_scanner():
    """Test the scanner with a sample image"""
    
    # Path to test image
    test_image = "/home/timkjr/dev/book-inventory/bookshelf-scanner/ai/dataset/images/img_1.jpg"
    
    if not os.path.exists(test_image):
        print(f"Test image not found: {test_image}")
        return
    
    print(f"Testing scanner with image: {test_image}")
    
    try:
        # Make request to main app's scanner endpoint
        with open(test_image, 'rb') as f:
            files = {'image': f}
            response = requests.post('http://localhost:8000/scan-bookshelf', files=files, timeout=60)
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Now check the Docker container output directory
        print("\n=== Checking Docker container output directory ===")
        os.system("docker compose exec bookshelf-scanner ls -la /app/output/")
        os.system("docker compose exec bookshelf-scanner ls -la /app/output/segmentation/")
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_scanner()