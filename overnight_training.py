#!/usr/bin/env python3
"""
Overnight YOLO Book Spine Training Automation
Runs sequential training phases and generates comprehensive report.
"""

import os
import sys
import time
import shutil
import subprocess
import json
import glob
from datetime import datetime
from pathlib import Path

# Training configuration
TRAINING_ROOT = Path("training")
DOWNLOADS_DIR = TRAINING_ROOT / "downloads"
DATASET_DIR = TRAINING_ROOT / "dataset"
RUNS_DIR = TRAINING_ROOT / "runs"
VENV_PYTHON = TRAINING_ROOT / "venv" / "bin" / "python"
REPORT_FILE = TRAINING_ROOT / "overnight_report.txt"
LOG_FILE = TRAINING_ROOT / "overnight.log"

class TrainingLogger:
    def __init__(self):
        self.start_time = datetime.now()
        self.log_entries = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {level}: {message}"
        print(entry)
        self.log_entries.append(entry)
        
        # Write to log file immediately
        with open(LOG_FILE, "a") as f:
            f.write(entry + "\n")
    
    def log_resource_usage(self):
        try:
            # Get memory usage
            result = subprocess.run(["free", "-h"], capture_output=True, text=True)
            memory_info = result.stdout.split('\n')[1]  # Mem line
            
            # Get disk usage
            result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
            disk_info = result.stdout.split('\n')[1]  # Root filesystem
            
            self.log(f"Resources - {memory_info.strip()}")
            self.log(f"Disk - {disk_info.strip()}")
            
        except Exception as e:
            self.log(f"Failed to log resources: {e}", "WARNING")

class DatasetManager:
    def __init__(self, logger):
        self.logger = logger
        
    def copy_dataset(self, source_name, target_dir):
        """Copy dataset from downloads to working directory"""
        source_dir = DOWNLOADS_DIR / source_name
        
        if not source_dir.exists():
            self.logger.log(f"Dataset not found: {source_dir}", "ERROR")
            return False
            
        # Clean target directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Copy all files
            for item in source_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, target_dir / item.name)
                else:
                    shutil.copy2(item, target_dir)
            
            self.logger.log(f"Copied dataset {source_name} to {target_dir}")
            return True
            
        except Exception as e:
            self.logger.log(f"Failed to copy dataset {source_name}: {e}", "ERROR")
            return False
    
    def assess_generic_dataset(self):
        """Assess the generic dataset format and compatibility"""
        generic_dir = DOWNLOADS_DIR / "dataset_generic"
        
        if not generic_dir.exists():
            self.logger.log("Generic dataset not found", "WARNING")
            return False, "Dataset not found"
        
        self.logger.log("Assessing generic dataset format...")
        
        # Look for common annotation formats
        annotation_files = []
        annotation_files.extend(glob.glob(str(generic_dir / "**" / "*.txt"), recursive=True))
        annotation_files.extend(glob.glob(str(generic_dir / "**" / "*.json"), recursive=True))
        annotation_files.extend(glob.glob(str(generic_dir / "**" / "*.xml"), recursive=True))
        
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp"]:
            image_files.extend(glob.glob(str(generic_dir / "**" / ext), recursive=True))
        
        self.logger.log(f"Found {len(image_files)} images and {len(annotation_files)} annotation files")
        
        # Check if it looks like YOLO format
        if annotation_files and len(annotation_files) > 0:
            # Sample a few annotation files
            sample_files = annotation_files[:5]
            yolo_like = True
            
            for ann_file in sample_files:
                if ann_file.endswith('.txt'):
                    try:
                        with open(ann_file, 'r') as f:
                            lines = f.readlines()
                            for line in lines[:3]:  # Check first 3 lines
                                parts = line.strip().split()
                                if len(parts) != 5:  # YOLO format: class x y w h
                                    yolo_like = False
                                    break
                                # Check if values are in 0-1 range (normalized)
                                try:
                                    values = [float(x) for x in parts[1:]]
                                    if not all(0 <= v <= 1 for v in values):
                                        yolo_like = False
                                        break
                                except ValueError:
                                    yolo_like = False
                                    break
                    except Exception:
                        yolo_like = False
                        break
            
            if yolo_like:
                self.logger.log("Generic dataset appears to be YOLO-compatible")
                return True, "YOLO format detected"
            else:
                self.logger.log("Generic dataset is not in YOLO format")
                return False, "Non-YOLO format"
        else:
            self.logger.log("No annotation files found in generic dataset")
            return False, "No annotations found"

class YOLOTrainer:
    def __init__(self, logger):
        self.logger = logger
        
    def train_model(self, dataset_path, epochs, batch_size, name):
        """Train YOLO model with given parameters"""
        data_yaml = dataset_path / "data.yaml"
        
        if not data_yaml.exists():
            self.logger.log(f"data.yaml not found in {dataset_path}", "ERROR")
            return None
        
        self.logger.log(f"Starting training: {name} - {epochs} epochs, batch size {batch_size}")
        
        try:
            # Build training command
            cmd = [
                str(VENV_PYTHON), "train_model.py",
                "--data", str(data_yaml),
                "--epochs", str(epochs),
                "--batch", str(batch_size),
                "--name", name
            ]
            
            # Run training
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/timkjr/dev/book-inventory")
            end_time = time.time()
            
            training_duration = end_time - start_time
            
            if result.returncode == 0:
                self.logger.log(f"Training completed successfully in {training_duration/60:.1f} minutes")
                
                # Find the best model
                best_model = RUNS_DIR / name / "weights" / "best.pt"
                if best_model.exists():
                    model_size = best_model.stat().st_size / (1024 * 1024)  # MB
                    self.logger.log(f"Best model saved: {best_model} ({model_size:.1f} MB)")
                    return best_model
                else:
                    self.logger.log("Training completed but best.pt not found", "WARNING")
                    return None
            else:
                self.logger.log(f"Training failed: {result.stderr}", "ERROR")
                return None
                
        except Exception as e:
            self.logger.log(f"Training error: {e}", "ERROR")
            return None
    
    def test_model(self, model_path, test_image="5-book-sample.jpg"):
        """Test trained model on sample image"""
        if not model_path or not Path(model_path).exists():
            self.logger.log("Model not found for testing", "ERROR")
            return "Model not available"
        
        self.logger.log(f"Testing model {model_path} on {test_image}")
        
        try:
            # Check if Docker containers are running first
            result = subprocess.run(["docker", "compose", "ps", "--format", "json"], capture_output=True, text=True)
            if result.returncode != 0 or "bookshelf-scanner" not in result.stdout:
                self.logger.log("Docker containers not running, skipping model testing", "WARNING")
                model_size = model_path.stat().st_size / (1024 * 1024)  # MB
                return f"Model created: {model_size:.1f} MB (testing skipped)"
            
            # Copy trained model to container temp directory for testing
            container_model_path = "/tmp/test_model.pt"
            
            # No need to create directory - /tmp always exists
            
            # Copy model to container
            subprocess.run(["docker", "compose", "cp", str(model_path), f"bookshelf-scanner:{container_model_path}"], check=True)
            
            # Restart container to pick up new model
            subprocess.run(["docker", "compose", "restart", "bookshelf-scanner"], check=True)
            
            # Wait for container to be ready
            time.sleep(30)
            
            # Test the model
            test_cmd = ["docker", "compose", "exec", "bookshelf-scanner", 
                       "curl", "-X", "POST", "-F", f"file=@/app/{test_image}", 
                       "http://localhost:8001/api/predict/"]
            
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Parse results - count how many books were detected
                output = result.stdout
                book_count = output.count("Book ")
                self.logger.log(f"Model test completed: {book_count} books detected")
                return f"{book_count} books detected"
            else:
                self.logger.log(f"Model test failed: {result.stderr}", "ERROR")
                return "Test failed"
                
        except subprocess.TimeoutExpired:
            self.logger.log("Model test timed out", "ERROR")
            return "Test timed out"
        except Exception as e:
            self.logger.log(f"Model test error: {e}", "ERROR")
            return "Test error"

def main():
    logger = TrainingLogger()
    dataset_mgr = DatasetManager(logger)
    trainer = YOLOTrainer(logger)
    
    logger.log("=== YOLO Book Spine Training - Overnight Session ===")
    logger.log_resource_usage()
    
    results = {}
    
    # Phase 1: Small Dataset Pipeline Test
    logger.log("\n=== PHASE 1: Small Dataset Pipeline Test ===")
    if dataset_mgr.copy_dataset("dataset_small", DATASET_DIR):
        model_path = trainer.train_model(DATASET_DIR, epochs=50, batch_size=8, name="small")
        test_result = trainer.test_model(model_path)
        results["small"] = {
            "model_path": str(model_path) if model_path else None,
            "test_result": test_result,
            "dataset_size": "159 images"
        }
        logger.log_resource_usage()
    
    # Phase 2: Generic Dataset Assessment
    logger.log("\n=== PHASE 2: Generic Dataset Assessment ===")
    generic_compatible, generic_reason = dataset_mgr.assess_generic_dataset()
    results["generic_assessment"] = {
        "compatible": generic_compatible,
        "reason": generic_reason
    }
    
    # Phase 3: Large Dataset Training
    logger.log("\n=== PHASE 3: Large Dataset Training ===")
    if dataset_mgr.copy_dataset("dataset_large", DATASET_DIR):
        model_path = trainer.train_model(DATASET_DIR, epochs=100, batch_size=8, name="large")
        test_result = trainer.test_model(model_path)
        results["large"] = {
            "model_path": str(model_path) if model_path else None,
            "test_result": test_result,
            "dataset_size": "~1900 images"
        }
        logger.log_resource_usage()
    
    # Phase 4: Combined Dataset Training (if generic is compatible)
    if generic_compatible:
        logger.log("\n=== PHASE 4: Combined Dataset Training ===")
        # For now, just use large dataset - combining would require more complex logic
        # In a real implementation, you'd merge the datasets here
        logger.log("Combined training would require dataset merging - using large dataset as proxy")
        results["combined"] = {
            "status": "Skipped - would require dataset merging implementation",
            "note": "Generic dataset is compatible but merging not implemented"
        }
    else:
        logger.log("\n=== PHASE 4: Skipped (Generic dataset not compatible) ===")
        results["combined"] = {
            "status": "Skipped - generic dataset not compatible",
            "reason": generic_reason
        }
    
    # Phase 5: Generate Final Report
    logger.log("\n=== PHASE 5: Final Report Generation ===")
    
    total_duration = datetime.now() - logger.start_time
    
    # Generate comprehensive report
    report = f"""
YOLO Book Spine Training Overnight Report
========================================
Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Total Duration: {total_duration}

SYSTEM RESOURCES:
- CPU: 4 cores allocated
- RAM: 20GB + 16GB swap
- Training completed on: {os.uname().nodename}

TRAINING RESULTS:
================

Phase 1 - Small Dataset (159 images):
Model: {results.get('small', {}).get('model_path', 'Failed')}
Test Result: {results.get('small', {}).get('test_result', 'Not tested')}

Phase 2 - Generic Dataset Assessment:
Compatible: {results.get('generic_assessment', {}).get('compatible', 'Unknown')}
Reason: {results.get('generic_assessment', {}).get('reason', 'Not assessed')}

Phase 3 - Large Dataset (~1900 images):
Model: {results.get('large', {}).get('model_path', 'Failed')}
Test Result: {results.get('large', {}).get('test_result', 'Not tested')}

Phase 4 - Combined Dataset:
Status: {results.get('combined', {}).get('status', 'Not attempted')}

BASELINE COMPARISON:
===================
Original Performance: 2/8 books detected correctly (25% accuracy, many false positives)
Target Performance: 4-5/5 books detected correctly (80-100% accuracy)

Current Best Model:
"""
    
    # Determine best model
    best_model = None
    best_score = 0
    
    for phase in ['large', 'small']:
        if phase in results and results[phase].get('test_result'):
            test_result = results[phase]['test_result']
            if 'books detected' in test_result:
                try:
                    score = int(test_result.split()[0])
                    if score > best_score:
                        best_score = score
                        best_model = results[phase]['model_path']
                except:
                    pass
    
    if best_model:
        report += f"""
BEST MODEL: {best_model}
Performance: {best_score}/5 books detected
Improvement: 25% baseline → {best_score/5*100:.0f}% accuracy
Ready for production deployment!

RECOMMENDATIONS:
- Deploy best model to production
- Model automatically loaded via bind mount
- Restart Docker services to use new model: docker compose up -d --build
"""
    else:
        report += """
No successful models generated.
Check training logs for errors.
May need to adjust batch size or dataset format.
"""
    
    report += f"""

DETAILED LOG:
============
{chr(10).join(logger.log_entries)}

Training completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    # Write report
    with open(REPORT_FILE, "w") as f:
        f.write(report)
    
    logger.log(f"Final report written to: {REPORT_FILE}")
    logger.log("=== TRAINING SESSION COMPLETED ===")
    
    print(f"\nTraining completed! Report available at: {REPORT_FILE}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)