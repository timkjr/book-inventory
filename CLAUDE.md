# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains two distinct but related projects:

1. **Personal Book Inventory System** - A FastAPI-based web application for managing personal book collections with lending tracking and metadata lookup capabilities
2. **Bookshelf Scanner** - An AI-powered system for detecting and identifying books from bookshelf images using computer vision and LLMs

## Project 1: Personal Book Inventory System

### Overview
This is a fully-featured Personal Book Inventory System built with FastAPI and SQLite. It provides a web interface for managing personal book collections with lending tracking and metadata lookup capabilities.

### Technology Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: SQLite with direct SQL queries
- **Frontend**: Jinja2 templates with vanilla JavaScript
- **Styling**: Custom CSS
- **Containerization**: Docker with Docker Compose
- **External APIs**: OpenLibrary and Google Books for metadata lookup

### Development Commands

#### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the main application
python main.py

# Access at http://localhost:8000
```

#### Scanner Integration
```bash
# Start the scanner backend service (required for scan functionality)
cd bookshelf-scanner/backend
poetry install
poetry run python run_server.py

# Access scanner service at http://localhost:8001
```

#### Docker Development (Recommended)
```bash
# Build and run all services (main inventory + scanner)
docker compose up -d

# View logs for all services
docker compose logs -f

# View logs for specific service
docker compose logs -f book-inventory
docker compose logs -f bookshelf-scanner

# Stop all services
docker compose down

# Rebuild services after code changes
docker compose up -d --build
```

#### Database
- Database file: `data/books.db`
- Automatic initialization on startup
- Migrations handled via try/except blocks in `init_database()`

### Architecture

#### Core Components

- **main.py**: Single-file FastAPI application containing all routes and business logic
- **Database**: SQLite with two tables:
  - `books`: Main book inventory with metadata
  - `settings`: Application configuration (library name, etc.)
- **Templates**: Jinja2 HTML templates in `templates/` directory
- **Static Files**: CSS and JavaScript in `static/` directory

#### Key Features

1. **Book Management**: Full CRUD operations for books
2. **Metadata Lookup**: Automatic book data retrieval from OpenLibrary and Google Books APIs
3. **Bookshelf Scanning**: AI-powered book detection from images using integrated scanner service
4. **Bulk Book Addition**: Add multiple books at once from scanned images
5. **Lending Tracking**: Track who borrowed books and when
6. **Search & Filtering**: Search by title, author, ISBN, or notes; filter by location/genre
7. **Export**: JSON export of entire library
8. **API Endpoints**: REST API for external integrations

#### Database Schema

The `books` table includes:
- Basic info: title, author, isbn, publisher, year, genre
- Physical tracking: location, condition
- Lending: loaned_to, loaned_date, due_date
- Metadata: cover_url, google_books_link, description, page_count
- System: id, added_date, notes

#### API Integration

- **OpenLibrary API**: Primary ISBN lookup source
- **Google Books API**: Enhanced metadata with covers and descriptions
- **Enhanced Lookup**: Combines both APIs for comprehensive book data

### File Structure

```
book-inventory/
├── main.py              # FastAPI application (single file)
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container definition
├── docker-compose.yml  # Multi-container setup
├── data/               # SQLite database storage
│   └── books.db
├── templates/          # Jinja2 HTML templates
│   ├── base.html       # Base template with navigation
│   ├── index.html      # Book list with search/filter
│   ├── add_book.html   # Add book form
│   ├── edit_book.html  # Edit book form
│   ├── book_detail.html # Book details view
│   ├── loaned.html     # Loaned books view
│   ├── scan_bookshelf.html # AI scanner interface
│   └── settings.html   # Settings form
└── static/            # CSS and JavaScript
    ├── style.css      # Custom styling
    └── script.js      # Frontend interactions
```

### Key Patterns

#### Database Connections
- Uses `get_db_connection()` helper with row factory
- Connections are opened/closed per request
- Try/except blocks for error handling

#### Metadata Lookup
- `enhanced_book_lookup()` combines multiple APIs
- Scoring system for Google Books search results
- Fallback chain: ISBN → Title+Author → Title only

#### Form Handling
- FastAPI Form dependencies for all user input
- Location dropdown with custom text input option
- Optional metadata lookup checkbox

#### Scanner Integration
- Service health checks before allowing scan operations
- Async HTTP client for scanner API communication
- Streaming response parsing for real-time book detection results
- Bulk book processing with metadata enhancement
- Error handling with fallback when scanner service unavailable

### Development Notes

- All code is contained in a single `main.py` file
- Database migrations are handled inline during startup
- No separate test suite currently exists
- Debug prints are used for Google Books API troubleshooting
- Main application runs on port 8000, scanner service on port 8001
- Scanner integration requires the bookshelf-scanner backend service
- Scanner service health checks are performed before allowing scan operations
- Docker Compose manages both services with proper networking and dependencies
- AI models are downloaded automatically on first run and cached in Docker volumes

### Docker Compose Issues Fixed (July 2024)

**Important:** Use `docker compose` (v2) commands, not `docker-compose` (v1).

Common issues and solutions:
1. **ContainerConfig errors**: Fixed by cleaning containers and rebuilding from scratch
2. **YOLO model download failures**: Pre-download during Docker build using correct URL
3. **llama-cpp-python architecture issues**: Rebuild from source with OpenBLAS
4. **Moondream model path issues**: Use absolute paths in container environment

If you encounter ContainerConfig errors:
```bash
docker compose down --volumes
docker system prune -f
docker compose up -d --build
```

The scanner service may take 5-10 minutes to build due to compiling llama-cpp-python from source.

## Project 2: Bookshelf Scanner

### Overview
An AI-powered system for detecting and identifying books from bookshelf images using computer vision (YOLO segmentation) and Large Language Models (Moondream2). The system consists of three main components working together to process bookshelf images and extract book metadata.

### Architecture
This is a multi-service application with separate AI, backend, and frontend components:

#### Components
1. **AI Service (Python, Poetry)**: 
   - YOLO segmentation for book detection
   - Moondream2 LLM for title/author extraction
   - Image preprocessing and rotation correction

2. **Backend Service (Python, FastAPI, Poetry)**:
   - REST API (`POST /api/predict`)
   - Asynchronous streaming responses
   - Integration with AI service

3. **Frontend Service (Angular, Bun)**:
   - File upload interface
   - Real-time streaming display
   - Modern SPA architecture

### Technology Stack
- **AI**: Python 3.12, YOLO 11x, Moondream2, Poetry
- **Backend**: FastAPI, Python 3.12, Poetry
- **Frontend**: Angular 18, Bun runtime
- **Models**: YOLO segmentation, Moondream2 LLM (quantized)

### Development Commands

#### Backend Service
```bash
cd bookshelf-scanner/backend
poetry config virtualenvs.in-project true
poetry install
poetry run fastapi dev src/main.py
# Access at http://localhost:8000/docs
```

#### Frontend Service
```bash
cd bookshelf-scanner/frontend
bun install
bun run start
# Access at http://localhost:8001
```

#### AI Service
```bash
cd bookshelf-scanner/ai
poetry install
# Used internally by backend service
```

### Workflow
1. User uploads bookshelf image via frontend
2. Backend receives image and sends to AI service
3. AI service processes image:
   - Segments books using YOLO
   - Extracts individual book spines
   - Uses Moondream2 to recognize titles/authors
4. Backend streams results back to frontend
5. Frontend displays segmented image and book data in real-time

### File Structure
```
bookshelf-scanner/
├── ai/                     # AI processing service
│   ├── src/bookscanner_ai/ # Core AI logic
│   ├── models/            # AI model files
│   └── dataset/           # Training/test images
├── backend/               # FastAPI backend
│   ├── src/               # Backend source code
│   └── models/            # Moondream2 model files
└── frontend/              # Angular frontend
    └── src/               # Frontend source code
```

### Key Features
- Real-time image processing with streaming results
- YOLO-based book spine detection and segmentation
- LLM-powered title/author recognition
- Asynchronous processing for better performance
- Modern web interface with live updates

## Repository Structure

```
book-inventory/
├── main.py                 # Main book inventory FastAPI app
├── requirements.txt        # Python dependencies for main app
├── Dockerfile             # Docker setup for main app
├── docker-compose.yml      # Multi-service Docker orchestration
├── .dockerignore          # Docker build optimization
├── data/books.db          # SQLite database (persistent volume)
├── templates/             # Jinja2 templates for main app
│   └── scan_bookshelf.html # AI scanner interface
├── static/               # CSS/JS for main app
└── bookshelf-scanner/    # Integrated AI-powered scanner project
    ├── .dockerignore     # Scanner Docker build optimization
    ├── ai/               # AI processing service
    ├── backend/          # FastAPI backend for scanner
    │   ├── Dockerfile    # Scanner service Docker setup
    │   └── run_server.py # Scanner service launcher
    └── frontend/         # Angular frontend (not used in Docker)
```

### Docker Architecture

The application uses a multi-service Docker architecture:

- **book-inventory**: Main application service (port 8000)
- **bookshelf-scanner**: AI scanner backend service (port 8001)
- **scanner-models**: Persistent volume for AI models
- **scanner-output**: Persistent volume for temporary processing files

Services communicate via Docker networking, with the main app automatically discovering the scanner service via the `SCANNER_SERVICE_URL` environment variable.

### Docker Compose Fixes Applied

**Key fixes for Docker Compose issues:**

1. **Removed obsolete version specification** - Docker Compose v2 doesn't need `version: '3.8'`
2. **Fixed YOLO model download** - Pre-download `yolo11x-seg.pt` during build from: `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x-seg.pt`
3. **Fixed llama-cpp-python compatibility** - Rebuild from source with CMAKE flags for proper architecture
4. **Fixed Moondream model paths** - Use absolute container paths: `/app/models/cache/moondream2`
5. **Added required build dependencies** - cmake, libopenblas-dev for compiling C++ extensions

**Current Status:**
- Main service: ✅ Working
- Scanner service: ⚠️ Takes 5-10 minutes to build (compiling llama-cpp-python)
- All Docker Compose configuration errors resolved

## Development Notes

### Main Book Inventory
- Single-file FastAPI application
- SQLite database with automatic migrations
- No separate test suite
- Runs on port 8000

### Bookshelf Scanner
- Multi-service architecture
- Poetry-based dependency management
- Modern JavaScript/TypeScript frontend
- AI model integration with quantized LLMs
- Backend runs on port 8000, frontend on port 8001

## NEVER FORGET
- READ YOUR OWN NOTES FIRST
- CREATE MEMORY FILES DURING LONG OPERATIONS
- DON'T LIE ABOUT CAPABILITIES
- USER EXPECTS ACCURACY, NOT GUESSING
