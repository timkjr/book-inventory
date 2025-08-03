from fastapi import FastAPI, Request, Form, HTTPException, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse, StreamingResponse
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import requests
import json
import os
import re
import asyncio
import aiohttp
from difflib import SequenceMatcher

app = FastAPI(title="Personal Book Inventory")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database setup
DATABASE = "data/books.db"

# Scanner service configuration
SCANNER_SERVICE_URL = os.getenv("SCANNER_SERVICE_URL", "http://localhost:8001")
SCANNER_API_URL = f"{SCANNER_SERVICE_URL}/api/predict/"

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

# Fuzzy matching helper functions for improved book search

def string_similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings using SequenceMatcher"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def normalize_string(s: str) -> str:
    """Normalize string for matching - remove common words, punctuation, etc."""
    if not s:
        return ""
    # Convert to lowercase and remove common punctuation
    s = s.lower().strip()
    # Remove common articles and prepositions that don't affect matching
    common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
    words = re.findall(r'\b\w+\b', s)  # Extract words, removing punctuation
    words = [word for word in words if word not in common_words or len(words) <= 2]  # Keep common words in short titles
    return ' '.join(words)

def fuzzy_title_match(search_title: str, book_title: str) -> tuple[float, str]:
    """Enhanced title matching with fuzzy logic"""
    if not search_title or not book_title:
        return 0.0, "no data"
    
    search_norm = normalize_string(search_title)
    book_norm = normalize_string(book_title)
    
    # Exact match (normalized)
    if search_norm == book_norm:
        return 1.0, "exact match"
    
    # Check if one is a substring of the other
    if search_norm in book_norm or book_norm in search_norm:
        return 0.9, "substring match"
    
    # Word order permutation check - sometimes AI gets word order wrong
    search_words = set(search_norm.split())
    book_words = set(book_norm.split())
    
    # If all search words are in book title (or vice versa)
    if search_words.issubset(book_words) or book_words.issubset(search_words):
        return 0.85, "word subset match"
    
    # Check word intersection ratio
    intersection = search_words.intersection(book_words)
    union = search_words.union(book_words)
    if union:
        word_ratio = len(intersection) / len(union)
        if word_ratio >= 0.6:  # 60% word overlap
            return 0.7 + (word_ratio - 0.6) * 0.375, f"word overlap ({word_ratio:.2f})"
    
    # Fallback to edit distance similarity
    similarity = string_similarity(search_norm, book_norm)
    if similarity >= 0.6:
        return similarity * 0.7, f"edit distance ({similarity:.2f})"
    
    return 0.0, "no match"

def fuzzy_author_match(search_author: str, book_author: str) -> tuple[float, str]:
    """Enhanced author matching with fuzzy logic"""
    if not search_author or not book_author:
        return 0.0 if search_author and book_author else 0.5, "missing data"  # Neutral if one is missing
    
    search_norm = normalize_string(search_author)
    book_norm = normalize_string(book_author)
    
    # Exact match
    if search_norm == book_norm:
        return 1.0, "exact match"
    
    # Last name matching (common for author searches)
    search_words = search_norm.split()
    book_words = book_norm.split()
    
    if search_words and book_words:
        # Check if last names match
        if search_words[-1] == book_words[-1]:
            return 0.9, "last name match"
        
        # Check if any significant word matches (length > 2)
        significant_matches = []
        for sw in search_words:
            for bw in book_words:
                if len(sw) > 2 and len(bw) > 2:
                    sim = string_similarity(sw, bw)
                    if sim >= 0.8:
                        significant_matches.append(sim)
        
        if significant_matches:
            avg_match = sum(significant_matches) / len(significant_matches)
            return avg_match * 0.8, f"name similarity ({avg_match:.2f})"
    
    # Edit distance similarity
    similarity = string_similarity(search_norm, book_norm)
    if similarity >= 0.6:
        return similarity * 0.7, f"edit distance ({similarity:.2f})"
    
    return 0.0, "no match"

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
                        
                        # Enhanced fuzzy matching
                        title_score, title_reason = fuzzy_title_match(title, book_title)
                        
                        # Convert to 0-3 scale for compatibility
                        title_match = title_score * 3
                        print(f"  Title: {title_reason} (score: {title_score:.2f} -> {title_match:.1f} points)")
                        
                        # Author matching with fuzzy logic
                        if author:
                            # Try matching against all authors in the book
                            author_scores = []
                            for book_author in book_authors:
                                auth_score, auth_reason = fuzzy_author_match(author, book_author)
                                author_scores.append((auth_score, auth_reason, book_author))
                            
                            # Use the best author match
                            if author_scores:
                                best_auth_score, best_auth_reason, matched_author = max(author_scores, key=lambda x: x[0])
                                author_match = best_auth_score * 3  # Convert to 0-3 scale
                                print(f"  Author: {best_auth_reason} vs '{matched_author}' (score: {best_auth_score:.2f} -> {author_match:.1f} points)")
                            else:
                                author_match = 0
                                print(f"  Author: No authors found (0 points)")
                        else:
                            author_match = 1  # Don't penalize if no author provided
                            print(f"  Author: No author provided (1 point)")
                        
                        # Calculate total score - title is more important, using continuous scores
                        total_score = title_score * 3 + (author_match / 3) * 1  # Weight title more heavily
                        print(f"  Total score: {total_score:.2f} (title:{title_score:.2f}*3 + author:{author_match/3:.2f}*1)")
                        
                        # Must have reasonable title match to be considered
                        if title_score >= 0.3 and total_score > best_score:
                            best_score = total_score
                            best_match = book
                            print(f"  -> New best match!")
                    
                    print(f"DEBUG: Best match score for this query: {best_score}")
                    
                    # If we found a good match, use it (lower threshold for fuzzy matching)
                    if best_match and best_score >= 1.5:  # More lenient threshold for enhanced fuzzy matching
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

# Scanner service communication functions

async def check_scanner_service():
    """Check if the scanner service is available"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SCANNER_SERVICE_URL, timeout=5) as response:
                return response.status == 200
    except Exception as e:
        print(f"Scanner service check failed: {e}")
        return False

def clean_book_text(text: str) -> str:
    """Clean book title/author text by removing quotes and extra punctuation"""
    if not text:
        return ""
    
    # Remove surrounding single and double quotes
    text = text.strip()
    if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
        text = text[1:-1]
    
    # Remove trailing periods that aren't part of abbreviations
    if text.endswith('.') and not text.endswith('Jr.') and not text.endswith('Sr.') and not text.endswith('Ph.D.'):
        text = text[:-1]
    
    return text.strip()

def parse_book_result(book_text: str) -> Optional[Dict[str, str]]:
    """Parse book result from scanner - handles both direct format and descriptive text"""
    if not book_text or book_text.strip() == "No book":
        return None
    
    # Remove "Book N: " prefix
    match = re.match(r'^Book \d+:\s*(.+)$', book_text.strip())
    if match:
        content = match.group(1)
    else:
        content = book_text.strip()
    
    print(f"DEBUG: Parsing content: '{content}'")
    
    # Strategy 1: Extract quoted titles and authors from descriptive text
    title = None
    author = None
    
    # Look for quoted title patterns - order matters, most specific first
    title_patterns = [
        r'(?:features|shows)\s+(?:the\s+)?title\s+"([^"]+)"',  # features the title "Book Name"
        r'(?:the\s+)?title\s+(?:of\s+the\s+book\s+)?(?:is\s+)?"([^"]+)"',  # title of the book is "Book Name"
        r'(?:with\s+the\s+)?title\s+"([^"]+)"',  # with the title "Book Name"
        r'(?:^|\s)title\s+(?:is\s+)?"([^"]+)"',  # title "Book Name" (standalone)
        r'"([^"]+)"\s+(?:written|by)',        # "Book Name" written/by
    ]
    
    for pattern in title_patterns:
        title_match = re.search(pattern, content, re.IGNORECASE)
        if title_match:
            title = clean_book_text(title_match.group(1))
            print(f"DEBUG: Extracted title via pattern '{pattern}': '{title}'")
            break
    
    # Look for quoted or named author patterns
    author_patterns = [
        r'(?:author|by)\s+(?:is\s+)?"([^"]+)"',    # author "Name"
        r'(?:author\'?s?\s+name)\s+(?:is\s+)?"([^"]+)"',  # author's name "Name"
        r'(?:by|author)\s+([A-Z][a-zA-Z\.\s]+?)(?:\s*$|\s+and\s|\s+&\s)',  # by AuthorName (unquoted, more flexible)
        r'(?:and\s+the\s+)?author\'?s?\s+name\s+is\s+"([^"]+)"',  # author's name is "Name"
    ]
    
    for pattern in author_patterns:
        author_match = re.search(pattern, content, re.IGNORECASE)
        if author_match:
            author = clean_book_text(author_match.group(1))
            print(f"DEBUG: Extracted author via pattern '{pattern}': '{author}'")
            break
    
    # Strategy 2: Fallback to original " by " splitting for direct format
    if not title:
        if " by " in content:
            parts = content.rsplit(" by ", 1)  # Split from the right to handle titles with "by"
            title = clean_book_text(parts[0])
            if not author:  # Only use if we didn't find author already
                author = clean_book_text(parts[1])
            print(f"DEBUG: Fallback split - Title: '{title}', Author: '{author}'")
        else:
            # If no "by" found, treat entire content as title
            title = clean_book_text(content)
            print(f"DEBUG: Using entire content as title: '{title}'")
    
    # Clean up extracted data
    if not title:
        return None
        
    if not author:
        author = ""
    
    print(f"DEBUG: Final result - Title: '{title}', Author: '{author}'")
    
    return {
        "title": title,
        "author": author
    }

async def call_scanner_api(image_file: UploadFile) -> List[Dict[str, str]]:
    """Call the scanner API and return list of detected books"""
    detected_books = []
    
    # Create form data
    form_data = aiohttp.FormData()
    form_data.add_field('file', await image_file.read(), 
                       filename=image_file.filename, 
                       content_type=image_file.content_type)
    
    try:
        print(f"Calling scanner API at: {SCANNER_API_URL}")
        # Configure client with larger chunk size for base64 images
        connector = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, 
                                       read_bufsize=1024*1024*10) as session:
            async with session.post(SCANNER_API_URL, data=form_data) as response:
                print(f"Scanner API response status: {response.status}")
                print(f"Scanner API response headers: {dict(response.headers)}")
                
                if response.status != 200:
                    response_text = await response.text()
                    print(f"Scanner API error response: {response_text}")
                    raise HTTPException(status_code=500, detail=f"Scanner service error: {response.status} - {response_text}")
                
                print("Reading streaming response from scanner...")
                line_count = 0
                async for line in response.content:
                    if line:
                        line_count += 1
                        try:
                            line_text = line.decode('utf-8').strip()
                            print(f"Scanner response line {line_count}: {line_text[:100]}...")
                            if line_text:
                                result = json.loads(line_text)
                                if result.get('success') and result.get('data'):
                                    data = result['data']
                                    # Skip the first response (segmented image)
                                    if not data.startswith('data:image/'):
                                        parsed_book = parse_book_result(data)
                                        if parsed_book:
                                            print(f"Parsed book: {parsed_book}")
                                            detected_books.append(parsed_book)
                        except json.JSONDecodeError as je:
                            print(f"JSON decode error on line {line_count}: {je}")
                            continue
                        except Exception as e:
                            print(f"Error processing scanner response line {line_count}: {e}")
                            continue
                
                print(f"Scanner API completed. Total lines: {line_count}, Books found: {len(detected_books)}")
                
    except aiohttp.ClientError as ce:
        print(f"HTTP client error calling scanner API: {ce}")
        raise HTTPException(status_code=500, detail=f"Scanner service connection error: {str(ce)}")
    except asyncio.TimeoutError:
        print("Scanner API timeout after 600 seconds (10 minutes)")
        raise HTTPException(status_code=500, detail="Scanner service timeout - AI processing took longer than 10 minutes")
    except Exception as e:
        print(f"Unexpected error calling scanner API: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scanner service error: {str(e)}")
    
    return detected_books

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

# Scanner routes
@app.get("/scan-bookshelf", response_class=HTMLResponse)
async def scan_bookshelf_form(request: Request):
    """Show bookshelf scanning form"""
    library_name = get_library_name()
    scanner_available = await check_scanner_service()
    locations = get_unique_locations()
    return templates.TemplateResponse("scan_bookshelf.html", {
        "request": request,
        "library_name": library_name,
        "scanner_available": scanner_available,
        "locations": locations
    })

@app.post("/scan-bookshelf")
async def scan_bookshelf(request: Request, image: UploadFile = File(...)):
    """Process bookshelf image and return detected books with metadata enhancement"""
    # Check if scanner service is available
    if not await check_scanner_service():
        raise HTTPException(status_code=503, detail="Scanner service is not available")
    
    # Validate file type
    if not image or not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Call scanner API to get raw detections
        detected_books = await call_scanner_api(image)
        
        # Only filter out exact duplicate titles (not partial matches)
        def is_exact_duplicate(title1: str, title2: str) -> bool:
            if not title1 or not title2:
                return False
            return title1.lower().strip() == title2.lower().strip()
        
        unique_books = []
        for book in detected_books:
            title = book.get("title", "").strip()
            if not any(is_exact_duplicate(title, existing.get("title", "")) for existing in unique_books):
                unique_books.append(book)
            else:
                print(f"DEBUG: Filtered exact duplicate: '{title}'")
        
        print(f"DEBUG: Original books: {len(detected_books)}, After filtering: {len(unique_books)}")
        
        # Enhance each book with metadata lookup
        enhanced_books = []
        for book in unique_books:
            title = book.get("title", "").strip()
            author = book.get("author", "").strip()
            
            # Perform metadata lookup to enhance the detection
            metadata = None
            if title:
                metadata = enhanced_book_lookup(title=title, author=author)
            
            # Create enhanced book data
            enhanced_book = {
                "title": title,
                "author": author or "Unknown Author",
                "original_title": title,  # Keep original for reference
                "original_author": author,  # Keep original for reference
                "confidence": "medium",  # Default confidence level
                "metadata_found": metadata is not None
            }
            
            # Add metadata if found
            if metadata:
                # Use metadata to potentially improve title/author
                metadata_title = metadata.get("title", "").strip()
                metadata_author = metadata.get("author", "").strip()
                
                # If metadata provides better quality data, suggest it
                if metadata_title and len(metadata_title) > len(title):
                    enhanced_book["suggested_title"] = metadata_title
                    enhanced_book["confidence"] = "high"
                    
                if metadata_author and metadata_author != "Unknown Author" and not author:
                    enhanced_book["suggested_author"] = metadata_author
                    enhanced_book["author"] = metadata_author
                    enhanced_book["confidence"] = "high"
                
                # Add additional metadata for preview
                enhanced_book.update({
                    "isbn": metadata.get("isbn"),
                    "publisher": metadata.get("publisher"),
                    "year": metadata.get("year"),
                    "genre": metadata.get("genre"),
                    "cover_url": metadata.get("cover_url"),
                    "description": metadata.get("description"),
                    "page_count": metadata.get("page_count")
                })
            
            enhanced_books.append(enhanced_book)
        
        # Return enhanced books for user confirmation
        return JSONResponse({
            "success": True,
            "detected_books": enhanced_books,
            "total_books": len(enhanced_books),
            "enhanced": True  # Flag to indicate metadata enhancement was applied
        })
    
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.post("/api/scan-and-add")
async def scan_and_add_books(request: Request, books_data: dict):
    """Add multiple books from scan results to inventory"""
    print(f"=== SCAN AND ADD DEBUG ===")
    print(f"Received books_data: {books_data}")
    
    books_to_add = books_data.get("books", [])
    print(f"Books to add: {books_to_add}")
    print(f"Number of books to add: {len(books_to_add)}")
    
    if not books_to_add:
        print("ERROR: No books provided in request")
        raise HTTPException(status_code=400, detail="No books provided")
    
    added_books = []
    errors = []
    
    for i, book_data in enumerate(books_to_add):
        print(f"\n--- Processing book {i+1}/{len(books_to_add)} ---")
        print(f"Book data: {book_data}")
        try:
            title = book_data.get("title", "").strip()
            author = book_data.get("author", "").strip()
            print(f"Extracted title: '{title}'")
            print(f"Extracted author: '{author}'")
            
            if not title:
                error_msg = f"Book missing title: {book_data}"
                print(f"ERROR: {error_msg}")
                errors.append(error_msg)
                continue
                
            if not author:
                author = "Unknown Author"
                print(f"Setting author to: '{author}'")
            
            # Enhanced metadata lookup
            print(f"Starting metadata lookup for: '{title}' by '{author}'")
            metadata = enhanced_book_lookup(title=title, author=author)
            print(f"Metadata lookup result: {metadata}")
            
            # Prepare book data for database insertion
            book_to_insert = {
                "title": title,
                "author": author,
                "isbn": metadata.get("isbn") if metadata else None,
                "publisher": metadata.get("publisher") if metadata else None,
                "year": metadata.get("year") if metadata else None,
                "genre": metadata.get("genre") if metadata else None,
                "location": book_data.get("location"),
                "condition": book_data.get("condition"),
                "notes": book_data.get("notes"),
                "cover_url": metadata.get("cover_url") if metadata else None,
                "google_books_link": metadata.get("google_books_link") if metadata else None,
                "description": metadata.get("description") if metadata else None,
                "page_count": metadata.get("page_count") if metadata else None
            }
            print(f"Prepared book_to_insert: {book_to_insert}")
            
            # Insert into database
            print("Attempting database insertion...")
            conn = get_db_connection()
            try:
                cursor = conn.execute("""
                    INSERT INTO books (title, author, isbn, publisher, year, genre, location, condition, notes, cover_url, google_books_link, description, page_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    book_to_insert["title"],
                    book_to_insert["author"],
                    book_to_insert["isbn"],
                    book_to_insert["publisher"],
                    book_to_insert["year"],
                    book_to_insert["genre"],
                    book_to_insert["location"],
                    book_to_insert["condition"],
                    book_to_insert["notes"],
                    book_to_insert["cover_url"],
                    book_to_insert["google_books_link"],
                    book_to_insert["description"],
                    book_to_insert["page_count"]
                ))
                
                book_id = cursor.lastrowid
                print(f"Database insertion successful! Book ID: {book_id}")
                conn.commit()
                conn.close()
                
                added_books.append({
                    "id": book_id,
                    "title": title,
                    "author": author
                })
                print(f"Successfully added book: {title} by {author}")
                
            except Exception as db_error:
                print(f"DATABASE ERROR: {str(db_error)}")
                conn.close()
                raise db_error
            
        except Exception as e:
            error_msg = f"Error adding book '{title if 'title' in locals() else 'unknown'}': {str(e)}"
            print(f"EXCEPTION: {error_msg}")
            import traceback
            traceback.print_exc()
            errors.append(error_msg)
    
    print(f"\n=== SCAN AND ADD SUMMARY ===")
    print(f"Total books processed: {len(books_to_add)}")
    print(f"Successfully added: {len(added_books)}")
    print(f"Errors: {len(errors)}")
    print(f"Added books: {added_books}")
    print(f"Errors list: {errors}")
    
    return JSONResponse({
        "success": True,
        "added_books": added_books,
        "errors": errors,
        "total_added": len(added_books)
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