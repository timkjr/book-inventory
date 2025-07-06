# Book Inventory App
---

# README.md
# Personal Book Inventory System

A simple, self-hosted web application for managing your personal book collection with lending tracking.

## Features

- 📚 Add and manage books in your personal library
- 🔍 Search books by title, author, or ISBN
- 📖 Automatic metadata lookup via ISBN (OpenLibrary)
- 📍 Track book locations (which shelf, room, etc.)
- 🔄 Lending management (who borrowed what, when)
- 📱 Responsive web interface
- 🐳 Docker ready for easy deployment
- 🔌 REST API for future integrations

## Quick Start

### Using Docker Compose (Recommended)

1. Clone or download the project files
2. Create the directory structure:
   ```
   book-inventory/
   ├── main.py
   ├── requirements.txt
   ├── Dockerfile
   ├── docker-compose.yml
   ├── templates/
   └── static/
   ```

3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Access the application at http://localhost:8000

### Manual Installation

1. Install Python 3.11+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## Configuration

### Environment Variables

- `TZ`: Timezone (default: UTC)

### Data Persistence

The SQLite database is stored in the `data/` directory. Make sure to backup this directory regularly.

## Usage

### Adding Books

1. Click "Add Book" in the navigation
2. Enter book details (Title and Author are required)
3. Optionally enter ISBN for automatic metadata lookup
4. Specify location and condition
5. Add any notes

### Lending Tracking

1. Edit a book
2. Fill in "Loaned To" field with person's name
3. Set loan date and optional due date
4. View all loaned books in the "Loaned Books" section

### API Endpoints

For integration with other tools (like computer vision systems):

- `POST /api/books` - Add a new book
- `GET /api/books` - Get all books (with optional search)

Example API usage:
```bash
curl -X POST "http://localhost:8000/api/books" \
     -H "Content-Type: application/json" \
     -d '{"title": "The Hobbit", "author": "J.R.R. Tolkien", "isbn": "9780547928227"}'
```

## Deployment on Homelab

### With Existing Reverse Proxy

If you're using Caddy, Traefik, or nginx:

1. Deploy the container on your desired port
2. Add a reverse proxy configuration
3. Example Caddy config:
   ```
   books.yourdomain.com {
       reverse_proxy localhost:8000
   }
   ```

### Security Considerations

- The application doesn't include authentication by default
- Consider putting it behind a reverse proxy with authentication
- Regular backups of the `data/` directory are recommended

## Development

### File Structure
```
book-inventory/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container definition
├── docker-compose.yml  # Multi-container setup
├── templates/          # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── add_book.html
│   ├── book_detail.html
│   ├── edit_book.html
│   └── loaned.html
└── static/            # CSS and JavaScript
    ├── style.css
    └── script.js
```

### Database Schema

The SQLite database includes these fields:
- `id` - Primary key
- `title` - Book title (required)
- `author` - Author name (required)
- `isbn` - ISBN-10 or ISBN-13
- `publisher` - Publisher name
- `year` - Publication year
- `genre` - Book genre/category
- `location` - Physical location (shelf, room, etc.)
- `condition` - Book condition
- `loaned_to` - Person who borrowed the book
- `loaned_date` - Date book was loaned
- `due_date` - Expected return date
- `notes` - Additional notes
- `cover_url` - URL to book cover image
- `added_date` - When book was added to system

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the system.