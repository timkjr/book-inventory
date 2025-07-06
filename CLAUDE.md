# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a fully-featured Personal Book Inventory System built with FastAPI and SQLite. It provides a web interface for managing personal book collections with lending tracking and metadata lookup capabilities.

## Technology Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: SQLite with direct SQL queries
- **Frontend**: Jinja2 templates with vanilla JavaScript
- **Styling**: Custom CSS
- **Containerization**: Docker with Docker Compose
- **External APIs**: OpenLibrary and Google Books for metadata lookup

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Access at http://localhost:8000
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Database
- Database file: `data/books.db`
- Automatic initialization on startup
- Migrations handled via try/except blocks in `init_database()`

## Architecture

### Core Components

- **main.py**: Single-file FastAPI application containing all routes and business logic
- **Database**: SQLite with two tables:
  - `books`: Main book inventory with metadata
  - `settings`: Application configuration (library name, etc.)
- **Templates**: Jinja2 HTML templates in `templates/` directory
- **Static Files**: CSS and JavaScript in `static/` directory

### Key Features

1. **Book Management**: Full CRUD operations for books
2. **Metadata Lookup**: Automatic book data retrieval from OpenLibrary and Google Books APIs
3. **Lending Tracking**: Track who borrowed books and when
4. **Search & Filtering**: Search by title, author, ISBN, or notes; filter by location/genre
5. **Export**: JSON export of entire library
6. **API Endpoints**: REST API for external integrations

### Database Schema

The `books` table includes:
- Basic info: title, author, isbn, publisher, year, genre
- Physical tracking: location, condition
- Lending: loaned_to, loaned_date, due_date
- Metadata: cover_url, google_books_link, description, page_count
- System: id, added_date, notes

### API Integration

- **OpenLibrary API**: Primary ISBN lookup source
- **Google Books API**: Enhanced metadata with covers and descriptions
- **Enhanced Lookup**: Combines both APIs for comprehensive book data

## File Structure

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
│   └── settings.html   # Settings form
└── static/            # CSS and JavaScript
    ├── style.css      # Custom styling
    └── script.js      # Frontend interactions
```

## Key Patterns

### Database Connections
- Uses `get_db_connection()` helper with row factory
- Connections are opened/closed per request
- Try/except blocks for error handling

### Metadata Lookup
- `enhanced_book_lookup()` combines multiple APIs
- Scoring system for Google Books search results
- Fallback chain: ISBN → Title+Author → Title only

### Form Handling
- FastAPI Form dependencies for all user input
- Location dropdown with custom text input option
- Optional metadata lookup checkbox

## Development Notes

- All code is contained in a single `main.py` file
- Database migrations are handled inline during startup
- No separate test suite currently exists
- Debug prints are used for Google Books API troubleshooting
- Application runs on port 8000 by default