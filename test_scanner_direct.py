#!/usr/bin/env python3
"""
Direct test of scanner API without the main app
"""

import requests
import os

def test_scanner_direct():
    """Test the scanner API directly"""
    
    # Path to test image
    test_image = "/home/timkjr/dev/book-inventory/bookshelf-scanner/ai/dataset/images/img_1.jpg"
    
    if not os.path.exists(test_image):
        print(f"Test image not found: {test_image}")
        return
    
    print(f"Testing scanner directly with image: {test_image}")
    
    try:
        # Test direct scanner API
        with open(test_image, 'rb') as f:
            files = {'file': f}
            print("Making request to scanner API...")
            response = requests.post('http://localhost:8001/api/predict', files=files, timeout=120)
        
        print(f"Response status: {response.status_code}")
        if response.status_code == 200:
            print("SUCCESS! Scanner processed the image")
            # Read the streaming response
            lines = response.text.strip().split('\n')
            for line in lines:
                if line.strip():
                    print(f"Scanner output: {line}")
        else:
            print(f"Error response: {response.text}")
        
        # Check output directory
        print("\n=== Checking output directory ===")
        os.system("docker compose exec bookshelf-scanner ls -la /app/output/")
        os.system("docker compose exec bookshelf-scanner ls -la /app/output/segmentation/")
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_scanner_direct()