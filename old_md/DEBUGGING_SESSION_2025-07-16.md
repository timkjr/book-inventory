# Bookshelf Scanner Debugging Session - July 16, 2025

## Project Context

This is a dual-component Personal Book Inventory System:
1. **Main Book Inventory** (FastAPI, SQLite) - manages book collections with lending tracking
2. **Bookshelf Scanner** (AI-powered) - detects books from images using YOLO + Moondream2 LLM

## Current Issue Being Debugged

**Problem**: The LLM is returning mixed/hallucinated book information - combining titles from one book with authors from completely different books.

**Example**: LLM output "The Shack by Wm. Paul Young" when "The Shack" and "Wm. Paul Young" are from different books on the shelf.

## Today's Debugging Journey

### Initial Problem (Session Start)
- LLM was returning **descriptive text** instead of clean "Title by Author" format
- Examples: `"The spine shows the title 'What's So Amazing About Grace?' written in white..."`
- Metadata lookup was working correctly but UI showed descriptions as titles

### First Fix: Enhanced Parsing Function (`main.py:470-542`)
**What we did**: Built complex regex patterns to extract titles/authors from descriptive text
**Result**: Successfully parsed descriptions but this was treating symptoms, not root cause

### Second Fix: Improved LLM Prompt (multiple attempts)
**Attempts**:
1. **Complex prompt** with detailed instructions → LLM ignored, kept being descriptive
2. **Simplified prompt** → Better but still inconsistent authors
3. **Current prompt** → More direct but now seeing book confusion

**Current prompt**:
```
Read the text on this book spine. Format: Title by Author
IMPORTANT: Always include "by Author" if you can see any author name.
[Examples...]
Response:
```

### Third Fix: YOLO Detection Improvements
**Problem identified**: 
- YOLO detecting 5 books but only processing 3-4
- Missing "The Shack" entirely  
- Duplicating "The Book of the Dun Cow"

**Changes made**:
- **Lowered confidence threshold**: 0.25 → 0.15 (now detecting 8 books vs 5)
- **Added deduplication**: Initially too aggressive, refined to only exact title matches

### Fourth Fix: Author Regex Pattern Bug
**Problem**: `"The Shack by Wm. Paul Young"` was being parsed as author="Wm" (truncated)
**Fix**: Updated regex from `([A-Z][a-z]+(?:\s+[A-Z][a-z\.]*)*)`
to `([A-Z][a-zA-Z\.\s]+?)(?:\s*$|\s+and\s|\s+&\s)` to capture full names with periods

## Current Status

### What's Working ✅
- **Main book inventory app** functioning correctly
- **Docker compose setup** stable with both services
- **Database operations** working (SQLite with automated migrations)
- **Metadata enhancement** via OpenLibrary + Google Books APIs working perfectly
- **Enhanced parsing function** handles both clean and descriptive LLM responses
- **YOLO detection** now finding more books (8 vs 5 initially)
- **Basic deduplication** preventing exact duplicate titles

### What's Broken ❌
- **LLM vision accuracy**: Mixing titles and authors from different books
- **Author detection consistency**: Often missing authors even when visible
- **Book identification accuracy**: "The Shack by Wm. Paul Young" example shows cross-book confusion

## Root Cause Hypothesis

The **core issue** appears to be **poor image segmentation quality**:

1. **YOLO segmentation** might be creating cropped images that:
   - Include portions of multiple books
   - Are too blurry/small for accurate text recognition
   - Have unclear boundaries between adjacent book spines

2. **Moondream2 LLM** is then:
   - Seeing partial/mixed text from multiple books
   - "Hallucinating" complete book info based on training data
   - Getting confused by example books in the prompt

## Next Steps for Tomorrow

### Immediate Debugging Actions Needed

1. **Examine Segmented Images**
   - Temporarily disable image cleanup in scanner
   - Look at actual cropped spine images being sent to LLM
   - Verify if YOLO is creating clean, single-book segments

2. **Test Vision Model Accuracy**
   - Try feeding known good spine images to LLM directly
   - Test if Moondream2 can accurately read clear spine text
   - Consider if we need a different vision model

3. **YOLO Parameter Tuning**
   - Check segmentation quality vs confidence threshold
   - Possibly adjust IoU (Intersection over Union) thresholds
   - Consider using different YOLO model (currently yolov8n-seg)

### Code Locations for Tomorrow

**Key files modified today**:
- `/home/timkjr/dev/book-inventory/main.py:470-542` - Enhanced parsing function
- `/home/timkjr/dev/book-inventory/bookshelf-scanner/ai/src/bookscanner_ai/predict.py:32-46` - LLM prompt
- `/home/timkjr/dev/book-inventory/bookshelf-scanner/ai/src/bookscanner_ai/predict.py:255` - YOLO confidence threshold (0.15)

**Cleanup function to disable**:
- Look for `cleanup()` method that deletes processed images
- Mentioned in logs as "Output directory cleaned up"
- Need to examine segmented spine images in `/app/output/` directory

### Alternative Solutions to Consider

1. **Different Vision Model**: 
   - Replace Moondream2 with more accurate text recognition model
   - Consider OCR + traditional computer vision approach
   - Test with larger/better vision models if compute allows

2. **Improved Segmentation**:
   - Try different YOLO models (YOLOv8m, YOLOv8l vs current YOLOv8n)
   - Adjust image preprocessing
   - Add post-processing to clean up segments

3. **Hybrid Approach**:
   - Use traditional OCR on segments for text extraction
   - Use LLM only for text cleaning/formatting
   - Combine multiple detection approaches

## Technical Architecture Summary

### Current Setup
- **Main App**: FastAPI on port 8000, SQLite database, metadata APIs
- **Scanner**: FastAPI on port 8001, YOLO 11x-seg + Moondream2 LLM
- **Docker**: Multi-service compose with persistent volumes for models
- **Communication**: HTTP API between services with streaming responses

### Environment Variables
- `SCANNER_SERVICE_URL=http://bookshelf-scanner:8001`
- `APPDATA_DIR` and `CACHE_DIR` for persistent storage

### Models Used
- **YOLO**: yolov8n-seg.pt (nano segmentation model)
- **LLM**: moondream2-text-model-Q4_K_M.gguf (quantized)
- **Confidence threshold**: 0.15 (lowered from 0.25)

## Sample Log Output (Current Behavior)

```
bookshelf-scanner  | 0: 896x320 8 books, 5886.3ms
book-inventory     | DEBUG: Original books: 8, After filtering: 7
book-inventory     | Scanner response: "Book 7: The Shack by Wm. Paul Young"
book-inventory     | DEBUG: Final result - Title: 'The Shack', Author: 'Wm. Paul Young'
```

**This shows the LLM is confidently returning mixed book information**, which strongly suggests the root issue is in image segmentation quality, not prompt engineering.

## Files Created During Session

- Enhanced parsing function with regex patterns for both clean and descriptive LLM output
- Conservative deduplication logic (exact matches only)
- Multiple prompt iterations trying to improve LLM consistency

## Docker Status

Both services running correctly:
- `book-inventory`: Healthy, port 8000
- `bookshelf-scanner`: Running, port 8001
- All changes applied and tested