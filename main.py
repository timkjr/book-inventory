from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
import sqlite3
from datetime import datetime
from typing import Optional
import requests
import json
import os

app = FastAPI(title="Personal Book Inventory")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database setup
DATABASE = "data/books.db"

def init_database():
    """Initialize the SQLite database"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    
    # Create books table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT,
            publisher TEXT,
            year INTEGER,
            genre TEXT,
            location TEXT,
            condition TEXT,
            loaned_to TEXT,
            loaned_date TEXT,
            due_date TEXT,
            notes TEXT,
            cover_url TEXT,
            google_books_link TEXT,
            description TEXT,
            page_count INTEGER,
            added_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create settings table for app configuration
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            library_name TEXT DEFAULT 'Personal Library',
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert default settings if none exist
    settings_count = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    if settings_count == 0:
        conn.execute("INSERT INTO settings (library_name) VALUES (?)", ("Personal Library",))
    
    # Add new columns if they don't exist (for existing databases)
    try:
        conn.execute("ALTER TABLE books ADD COLUMN google_books_link TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        conn.execute("ALTER TABLE books ADD COLUMN description TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        conn.execute("ALTER TABLE books ADD COLUMN page_count INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_unique_locations():
    """Get all unique locations from existing books"""
    conn = get_db_connection()
    locations = conn.execute("""
        SELECT DISTINCT location FROM books 
        WHERE location IS NOT NULL AND location != '' 
        ORDER BY location
    """).fetchall()
    conn.close()
    return [loc['location'] for loc in locations]

def get_unique_genres():
    """Get all unique genres from existing books"""
    conn = get_db_connection()
    genres = conn.execute("""
        SELECT DISTINCT genre FROM books 
        WHERE genre IS NOT NULL AND genre != '' 
        ORDER BY genre
    """).fetchall()
    conn.close()
    return [genre['genre'] for genre in genres]

def get_library_name():
    """Get the current library name from settings"""
    conn = get_db_connection()
    result = conn.execute("SELECT library_name FROM settings LIMIT 1").fetchone()
    conn.close()
    return result['library_name'] if result else "Personal Library"

def update_library_name(new_name: str):
    """Update the library name in settings"""
    conn = get_db_connection()
    conn.execute("UPDATE settings SET library_name = ?, updated_date = CURRENT_TIMESTAMP WHERE id = 1", (new_name,))
    conn.commit()
    conn.close()

def lookup_isbn(isbn: str):
    """Lookup book metadata from OpenLibrary using ISBN"""
    try:
        # Clean ISBN
        isbn = isbn.replace("-", "").replace(" ", "")
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            key = f"ISBN:{isbn}"
            if key in data:
                book_data = data[key]
                return {
                    "title": book_data.get("title", ""),
                    "author": ", ".join([author["name"] for author in book_data.get("authors", [])]),
                    "publisher": ", ".join([pub["name"] for pub in book_data.get("publishers", [])]),
                    "year": book_data.get("publish_date", ""),
                    "cover_url": book_data.get("cover", {}).get("medium", ""),
                    "isbn": isbn,
                    "source": "openlibrary"
                }
    except Exception as e:
        print(f"ISBN lookup error: {e}")
    return None

def search_google_books(title: str, author: str = None):
    """Search Google Books API by title and author with improved matching"""
    try:
        # Try multiple query strategies in order of preference
        queries_to_try = []
        
        if author:
            # Strategy 1: Simple combined search (often works better)
            queries_to_try.append(f"{title} {author}")
            
            # Strategy 2: Title with author (less strict)
            queries_to_try.append(f'intitle:{title} inauthor:{author}')
            
            # Strategy 3: Just title if author search fails
            queries_to_try.append(f'intitle:{title}')
        else:
            queries_to_try.append(f'intitle:{title}')
            queries_to_try.append(f'{title}')
        
        url = "https://www.googleapis.com/books/v1/volumes"
        
        for query_attempt, query in enumerate(queries_to_try):
            print(f"DEBUG: Attempt {query_attempt + 1}: Trying query '{query}'")
            
            params = {
                "q": query,
                "maxResults": 10,
                "fields": "items(id,volumeInfo(title,authors,publisher,publishedDate,industryIdentifiers,imageLinks,canonicalVolumeLink,description,pageCount,categories))"
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "items" in data and len(data["items"]) > 0:
                    print(f"DEBUG: Query '{query}' returned {len(data['items'])} results")
                    
                    # Find the best match
                    best_match = None
                    best_score = 0
                    
                    for i, item in enumerate(data["items"]):
                        book = item["volumeInfo"]
                        book_title = book.get("title", "").lower()
                        book_authors = [auth.lower() for auth in book.get("authors", [])]
                        
                        print(f"DEBUG: Result {i+1}: '{book.get('title', '')}' by {book.get('authors', [])}")
                        
                        # Calculate match score
                        title_match = 0
                        author_match = 0
                        
                        # Title matching - more flexible
                        title_lower = title.lower().strip()
                        if title_lower == book_title:
                            title_match = 3  # Exact match
                            print(f"  Title: Exact match (3 points)")
                        elif book_title.startswith(title_lower) or title_lower in book_title:
                            title_match = 2  # Good match
                            print(f"  Title: Good match (2 points)")
                        elif any(word in book_title for word in title_lower.split() if len(word) > 3):
                            title_match = 1  # Partial match
                            print(f"  Title: Partial match (1 point)")
                        else:
                            print(f"  Title: No match (0 points)")
                        
                        # Author matching (if provided)
                        if author:
                            author_lower = author.lower().strip()
                            author_words = [word for word in author_lower.split() if len(word) > 2]
                            
                            for book_author in book_authors:
                                # Check for exact match
                                if author_lower == book_author:
                                    author_match = 3
                                    print(f"  Author: Exact match (3 points)")
                                    break
                                # Check for lastname match (common case)
                                elif (author_words and book_author.split() and 
                                      author_words[-1] == book_author.split()[-1]):
                                    author_match = 2
                                    print(f"  Author: Last name match (2 points)")
                                    break
                                # Check for partial name match
                                elif any(word in book_author for word in author_words):
                                    if author_match < 1:  # Don't downgrade
                                        author_match = 1
                                        print(f"  Author: Partial match (1 point)")
                            
                            if author_match == 0:
                                print(f"  Author: No match (0 points)")
                        else:
                            author_match = 1  # Don't penalize if no author provided
                            print(f"  Author: No author provided (1 point)")
                        
                        # Calculate total score - title is more important
                        total_score = title_match * 2 + author_match * 1
                        print(f"  Total score: {total_score} (title:{title_match}*2 + author:{author_match}*1)")
                        
                        # Must have some title match to be considered
                        if title_match > 0 and total_score > best_score:
                            best_score = total_score
                            best_match = book
                            print(f"  -> New best match!")
                    
                    print(f"DEBUG: Best match score for this query: {best_score}")
                    
                    # If we found a good match, use it
                    if best_match and best_score >= 3:  # Slightly higher threshold for better matches
                        book = best_match
                        
                        # Extract ISBN (prefer ISBN-13, fallback to ISBN-10)
                        isbn = None
                        identifiers = book.get("industryIdentifiers", [])
                        for identifier in identifiers:
                            if identifier["type"] == "ISBN_13":
                                isbn = identifier["identifier"]
                                break
                            elif identifier["type"] == "ISBN_10":
                                isbn = identifier["identifier"]
                        
                        # Get the best cover image available
                        cover_url = None
                        image_links = book.get("imageLinks", {})
                        for size in ["extraLarge", "large", "medium", "small", "thumbnail"]:
                            if size in image_links:
                                cover_url = image_links[size].replace("http://", "https://")
                                break
                        
                        # Parse publication year
                        pub_date = book.get("publishedDate", "")
                        year = None
                        if pub_date:
                            try:
                                year = int(pub_date.split("-")[0])
                            except:
                                pass
                        
                        # Get first category as genre
                        categories = book.get("categories", [])
                        genre = categories[0] if categories else None
                        
                        print(f"DEBUG: SUCCESS! Returning match for '{book.get('title')}' by {book.get('authors')} (score: {best_score})")
                        
                        return {
                            "title": book.get("title", ""),
                            "author": ", ".join(book.get("authors", [])),
                            "publisher": book.get("publisher", ""),
                            "year": year,
                            "isbn": isbn,
                            "cover_url": cover_url,
                            "google_books_link": book.get("canonicalVolumeLink", ""),
                            "description": book.get("description", ""),
                            "page_count": book.get("pageCount"),
                            "genre": genre,
                            "source": "google_books",
                            "match_score": best_score
                        }
                    else:
                        print(f"DEBUG: Query '{query}' didn't produce good enough matches (best: {best_score})")
                        # Continue to next query strategy
                else:
                    print(f"DEBUG: Query '{query}' returned no results")
            else:
                print(f"DEBUG: Query '{query}' failed with status {response.status_code}")
        
        print(f"DEBUG: All query strategies failed. No good match found.")
        return None
        
    except Exception as e:
        print(f"Google Books search error: {e}")
    return None

def enhanced_book_lookup(title: str = None, author: str = None, isbn: str = None):
    """Enhanced book lookup that tries multiple sources"""
    result = None
    
    # If ISBN is provided, try that first
    if isbn:
        result = lookup_isbn(isbn)
        if result:
            # Enhance with Google Books data if available
            google_data = search_google_books(result["title"], result["author"])
            if google_data:
                # Merge data, preferring Google Books for some fields
                result.update({
                    "cover_url": google_data.get("cover_url") or result.get("cover_url"),
                    "google_books_link": google_data.get("google_books_link", ""),
                    "description": google_data.get("description", ""),
                    "page_count": google_data.get("page_count"),
                    "genre": google_data.get("genre") or result.get("genre")
                })
            return result
    
    # If no ISBN or ISBN lookup failed, search by title + author
    if title:
        result = search_google_books(title, author)
        if result:
            return result
    
    return None

@app.on_event("startup")
async def startup_event():
    init_database()

@app.get("/favicon.ico")
async def favicon():
    """Simple favicon response to stop 404 errors"""
    return Response(content="", media_type="image/x-icon")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, search: Optional[str] = None, view: Optional[str] = None, filter_value: Optional[str] = None):
    """Home page with book list and filtering options"""
    conn = get_db_connection()
    
    # Base query
    base_query = "SELECT * FROM books"
    params = []
    where_conditions = []
    
    # Add search condition
    if search:
        where_conditions.append("(title LIKE ? OR author LIKE ? OR isbn LIKE ? OR notes LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param, search_param])
    
    # Add view filtering
    if view and filter_value:
        if view == "location":
            where_conditions.append("location = ?")
            params.append(filter_value)
        elif view == "genre":
            where_conditions.append("genre = ?")
            params.append(filter_value)
    
    # Build final query
    if where_conditions:
        query = f"{base_query} WHERE {' AND '.join(where_conditions)} ORDER BY added_date DESC"
    else:
        query = f"{base_query} ORDER BY added_date DESC"
    
    books = conn.execute(query, params).fetchall()
    
    # Get unique values for filtering
    locations = get_unique_locations()
    genres = get_unique_genres()
    
    conn.close()
    library_name = get_library_name()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "books": books, 
        "search": search,
        "view": view,
        "filter_value": filter_value,
        "locations": locations,
        "genres": genres,
        "library_name": library_name
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_form(request: Request):
    """Show settings form"""
    library_name = get_library_name()
    return templates.TemplateResponse("settings.html", {
        "request": request, 
        "library_name": library_name
    })

@app.post("/settings")
async def update_settings(library_name: str = Form(...)):
    """Update application settings"""
    update_library_name(library_name)
    return RedirectResponse(url="/", status_code=303)

@app.get("/export")
async def export_library():
    """Export entire library as JSON"""
    conn = get_db_connection()
    books = conn.execute("SELECT * FROM books ORDER BY added_date DESC").fetchall()
    settings = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()
    
    # Convert to list of dicts
    books_list = []
    for book in books:
        books_list.append(dict(book))
    
    export_data = {
        "library_name": settings['library_name'] if settings else "Personal Library",
        "export_date": datetime.now().isoformat(),
        "total_books": len(books_list),
        "books": books_list
    }
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"book_library_export_{timestamp}.json"
    
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/json"
        }
    )

@app.get("/add", response_class=HTMLResponse)
async def add_book_form(request: Request):
    """Show add book form"""
    library_name = get_library_name()
    locations = get_unique_locations()
    return templates.TemplateResponse("add_book.html", {
        "request": request,
        "library_name": library_name,
        "locations": locations
    })

@app.post("/add")
async def add_book(
    title: str = Form(...),
    author: str = Form(...),
    isbn: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    genre: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    location_text: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    lookup_metadata: Optional[str] = Form(None)
):
    """Add a new book"""
    
    # Handle location dropdown vs text input
    if location == "__new__" and location_text:
        location = location_text.strip()
    elif not location:
        location = None
    
    # Enhanced metadata lookup
    cover_url = None
    google_books_link = None
    description = None
    page_count = None
    
    if lookup_metadata:
        # Clean up ISBN if provided
        clean_isbn = None
        if isbn:
            clean_isbn = isbn.replace("-", "").replace(" ", "")
        
        metadata = enhanced_book_lookup(title=title, author=author, isbn=clean_isbn)
        if metadata:
            # Only override empty fields
            if not title.strip():
                title = metadata["title"]
            if not author.strip():
                author = metadata["author"]
            if not publisher:
                publisher = metadata["publisher"]
            if not year and metadata.get("year"):
                year = metadata["year"]
            if not genre:
                genre = metadata["genre"]
            if not isbn:
                isbn = metadata.get("isbn")
            
            # Always update these enhanced fields
            cover_url = metadata.get("cover_url")
            google_books_link = metadata.get("google_books_link")
            description = metadata.get("description")
            page_count = metadata.get("page_count")
    
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO books (title, author, isbn, publisher, year, genre, location, condition, 
                          notes, cover_url, google_books_link, description, page_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, author, isbn, publisher, year, genre, location, condition, notes, 
          cover_url, google_books_link, description, page_count))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/book/{book_id}", response_class=HTMLResponse)
async def view_book(request: Request, book_id: int):
    """View book details"""
    conn = get_db_connection()
    try:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    library_name = get_library_name()
    return templates.TemplateResponse("book_detail.html", {
        "request": request, 
        "book": book,
        "library_name": library_name
    })

@app.get("/edit/{book_id}", response_class=HTMLResponse)
async def edit_book_form(request: Request, book_id: int):
    """Show edit book form"""
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    library_name = get_library_name()
    locations = get_unique_locations()
    
    return templates.TemplateResponse("edit_book.html", {
        "request": request, 
        "book": book,
        "library_name": library_name,
        "locations": locations
    })

@app.post("/edit/{book_id}")
async def edit_book(
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    isbn: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    genre: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    location_text: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    loaned_to: Optional[str] = Form(None),
    loaned_date: Optional[str] = Form(None),
    due_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    lookup_details: Optional[str] = Form(None)
):
    """Update book details"""
    
    # Handle location dropdown vs text input
    if location == "__new__" and location_text:
        location = location_text.strip()
    elif not location:
        location = None
    
    # If lookup_details is checked, perform metadata lookup first
    if lookup_details:
        # Clean up ISBN if provided
        clean_isbn = None
        if isbn:
            clean_isbn = isbn.replace("-", "").replace(" ", "")
        
        # Perform lookup
        metadata = enhanced_book_lookup(title=title, author=author, isbn=clean_isbn)
        
        if metadata:
            # Only update empty fields for basic info
            if not publisher and metadata.get("publisher"):
                publisher = metadata["publisher"]
            if not year and metadata.get("year"):
                year = metadata["year"]
            if not genre and metadata.get("genre"):
                genre = metadata["genre"]
            if not isbn and metadata.get("isbn"):
                isbn = metadata["isbn"]
            
            # For the enhanced fields, we need to update them in the database separately
            conn = get_db_connection()
            enhanced_updates = {}
            
            if metadata.get("cover_url"):
                enhanced_updates['cover_url'] = metadata["cover_url"]
            if metadata.get("google_books_link"):
                enhanced_updates['google_books_link'] = metadata["google_books_link"]
            if metadata.get("description"):
                enhanced_updates['description'] = metadata["description"]
            if metadata.get("page_count"):
                enhanced_updates['page_count'] = metadata["page_count"]
            
            if enhanced_updates:
                set_clause = ", ".join([f"{key} = ?" for key in enhanced_updates.keys()])
                values = list(enhanced_updates.values()) + [book_id]
                conn.execute(f"UPDATE books SET {set_clause} WHERE id = ?", values)
                conn.commit()
            conn.close()
    
    # Update the main book fields
    conn = get_db_connection()
    conn.execute("""
        UPDATE books SET 
        title=?, author=?, isbn=?, publisher=?, year=?, genre=?, 
        location=?, condition=?, loaned_to=?, loaned_date=?, due_date=?, notes=?
        WHERE id=?
    """, (title, author, isbn, publisher, year, genre, location, condition, 
          loaned_to, loaned_date, due_date, notes, book_id))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url=f"/book/{book_id}", status_code=303)

@app.post("/delete/{book_id}")
async def delete_book(book_id: int):
    """Delete a book"""
    conn = get_db_connection()
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/loaned", response_class=HTMLResponse)
async def loaned_books(request: Request):
    """View currently loaned books"""
    conn = get_db_connection()
    books = conn.execute("""
        SELECT * FROM books 
        WHERE loaned_to IS NOT NULL AND loaned_to != ''
        ORDER BY loaned_date DESC
    """).fetchall()
    conn.close()
    
    library_name = get_library_name()
    return templates.TemplateResponse("loaned.html", {
        "request": request, 
        "books": books,
        "library_name": library_name
    })

# API endpoints for future computer vision integration
@app.post("/api/books")
async def api_add_book(book_data: dict):
    """API endpoint to add a book - for computer vision integration"""
    title = book_data.get("title", "")
    author = book_data.get("author", "")
    isbn = book_data.get("isbn")
    
    if not title or not author:
        raise HTTPException(status_code=400, detail="Title and author are required")
    
    # Enhanced metadata lookup
    cover_url = None
    google_books_link = None
    description = None
    page_count = None
    publisher = book_data.get("publisher")
    year = book_data.get("year")
    genre = book_data.get("genre")
    
    # Always try to enhance with metadata
    metadata = enhanced_book_lookup(title=title, author=author, isbn=isbn)
    if metadata:
        if not publisher:
            publisher = metadata.get("publisher")
        if not year:
            year = metadata.get("year")
        if not genre:
            genre = metadata.get("genre")
        if not isbn:
            isbn = metadata.get("isbn")
        
        cover_url = metadata.get("cover_url")
        google_books_link = metadata.get("google_books_link")
        description = metadata.get("description")
        page_count = metadata.get("page_count")
    
    conn = get_db_connection()
    cursor = conn.execute("""
        INSERT INTO books (title, author, isbn, publisher, year, genre, cover_url, 
                          google_books_link, description, page_count, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, author, isbn, publisher, year, genre, cover_url, 
          google_books_link, description, page_count, book_data.get("notes", "Added via API")))
    book_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": book_id, "message": "Book added successfully", "metadata_found": metadata is not None}

@app.get("/api/books")
async def api_get_books(search: Optional[str] = None):
    """API endpoint to get books"""
    conn = get_db_connection()
    
    if search:
        books = conn.execute("""
            SELECT * FROM books 
            WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?
            ORDER BY added_date DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        books = conn.execute("SELECT * FROM books ORDER BY added_date DESC").fetchall()
    
    conn.close()
    
    # Convert to list of dicts
    result = []
    for book in books:
        result.append(dict(book))
    
    return {"books": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)