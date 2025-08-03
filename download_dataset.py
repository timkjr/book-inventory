#!/usr/bin/env python3
"""Download Roboflow book spine dataset for training."""

from roboflow import Roboflow
import os

# Initialize Roboflow (no API key needed for public datasets)
rf = Roboflow()

# Get the book spine dataset
project = rf.workspace("yoloscript").project("books_spines")
dataset = project.version(1).download("yolov11", location="./book_spine_dataset")

print("Dataset downloaded successfully!")
print(f"Dataset location: ./book_spine_dataset")
print("Dataset structure:")
os.system("find ./book_spine_dataset -type f -name '*.yaml' -exec cat {} \\;")