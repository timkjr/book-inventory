#!/usr/bin/env python3
"""
Train YOLOv11n-seg model for book spine detection.

Usage:
    source training/venv/bin/activate
    python train_model.py [--epochs 50] [--imgsz 640]
"""

import os
import argparse
from pathlib import Path
from ultralytics import YOLO

def train_book_spine_model(epochs=50, imgsz=640, batch_size=16, name="train", data_yaml="training/dataset/data.yaml"):
    """Train YOLO model for book spine detection."""
    
    # Check if dataset exists
    if not os.path.exists(data_yaml):
        print(f"Dataset configuration not found: {data_yaml}")
        print("Please set up your dataset first with images and annotations.")
        print("\nDataset structure should be:")
        print("training/dataset/")
        print("├── data.yaml")
        print("├── train/")
        print("│   ├── images/")
        print("│   └── labels/")
        print("├── valid/")
        print("│   ├── images/")
        print("│   └── labels/")
        print("└── test/")
        print("    ├── images/")
        print("    └── labels/")
        return
    
    # Check if base model exists
    base_model = "training/models/yolo11n-seg.pt"
    if not os.path.exists(base_model):
        print(f"Base model not found: {base_model}")
        print("Please download the base model first.")
        return
    
    print(f"Starting training with:")
    print(f"  Base model: {base_model}")
    print(f"  Dataset: {data_yaml}")
    print(f"  Epochs: {epochs}")
    print(f"  Image size: {imgsz}")
    
    # Initialize model
    model = YOLO(base_model)
    
    # Create output directory
    os.makedirs("training/runs", exist_ok=True)
    
    # Train the model
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        project="training/runs",
        name=name,
        exist_ok=True,
        save=True,
        plots=True,
        val=True,
        verbose=True
    )
    
    # Check if training completed successfully
    best_model = f"training/runs/{name}/weights/best.pt"
    if os.path.exists(best_model):
        print(f"\n✅ Training completed successfully!")
        print(f"Best model saved to: {best_model}")
        print(f"Model size: {os.path.getsize(best_model) / 1024 / 1024:.1f} MB")
        print(f"\nTo test the trained model:")
        print(f"1. Restart Docker services: docker compose up -d --build")
        print(f"2. Test with your bookshelf image")
        print(f"\nThe container will automatically use the trained model.")
    else:
        print(f"\n❌ Training may have failed. Check training/runs/{name}/ for logs.")

def main():
    parser = argparse.ArgumentParser(description="Train YOLO model for book spine detection")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--name", type=str, default="train", help="Training run name")
    parser.add_argument("--data", type=str, default="training/dataset/data.yaml", 
                       help="Path to dataset YAML file")
    
    args = parser.parse_args()
    
    train_book_spine_model(
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch_size=args.batch,
        name=args.name,
        data_yaml=args.data
    )

if __name__ == "__main__":
    main()