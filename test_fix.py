#!/usr/bin/env python3
"""Quick test to verify overnight_training.py can find existing models"""
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append('.')
from overnight_training import YOLOTrainer, TrainingLogger

def test_model_detection():
    """Test if the script can find existing trained models"""
    logger = TrainingLogger()
    trainer = YOLOTrainer(logger)
    
    # Check if existing models can be found
    runs_dir = Path("training/runs")
    
    for model_dir in ["small", "large"]:
        expected_path = runs_dir / model_dir / "weights" / "best.pt"
        if expected_path.exists():
            print(f"✅ Found model: {expected_path}")
            size_mb = expected_path.stat().st_size / (1024 * 1024)
            print(f"   Size: {size_mb:.1f} MB")
        else:
            print(f"❌ Missing model: {expected_path}")

if __name__ == "__main__":
    print("=== Testing Model Detection ===")
    test_model_detection()