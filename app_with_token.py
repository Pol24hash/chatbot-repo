import requests
import json
import math
import re
import difflib
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client

LOGFILE = Path("token_log.jsonl")

# Supabase setup — replace with your real project values
SUPABASE_URL = "https://muddfgkpzvfdhljkeprn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im11ZGRmZ2twenZmZGhsamtlcHJuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEyMjYzODcsImV4cCI6MjA3NjgwMjM4N30.g7a_QcoAcbsGLvYkylsLW52-PfhuHwmERKrBCkbpErI"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Token counting functions
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except Exception:
    TIKTOKEN_AVAILABLE = False

def count_tokens_with_tiktoken(text: str, encoding_name: str = "cl100k_base") -> int:
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))

def approximate_token_count(text: str) -> int:
    return math.ceil(len(text) / 4)

def count_tokens(text: str) -> int:
    if TIKTOKEN_AVAILABLE:
        try:
            return count_tokens_with_tiktoken(text)
        except Exception:
            return approximate_token_count(text)
    else:
        return approximate_token_count(text)

def call_library_bot(prompt: str) -> str:
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "library-bot", "prompt": prompt, "stream": False, "options": {"num_predict": 60}},
            timeout=30
        )
        if res.ok:
            return res.json().get("response", "").strip()
        else:
            return f"Error: {res.status_code}"
    except requests.Timeout:
        return "Sorry, the response took too long. Please try again."
    except Exception as e:
        return f"Error: {e}"

def log_entry(entry: dict):
    with LOGFILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def fuzzy_match_word(word, possibilities, cutoff=0.75):
    matches = difflib.get_close_matches(word.lower(), possibilities, n=1, cutoff=cutoff)
    return matches[0] if matches else None

def fuzzy_match_title(prompt, all_titles, cutoff=0.7):
    prompt_lower = prompt.lower().strip(" ?!")  # Strip trailing punctuation
    titles_lower = [t.lower() for t in all_titles]

    # Extended patterns to capture title phrase after different query prefixes
    patterns = [
        r'is (.+) available',
        r'is (.+) still available',
        r'who is the author of (.+)',
        r'author of (.+)',
        r'what is the isbn of (.+)',
        r'what\'?s the isbn of (.+)',
        r'isbn of (.+)',
        r'what year (.+) publish(ed)?',
        r'tell me about (.+)',
        r'give me (.+)',   # sometimes used for descriptions
        r'(.+)'  # fallback
    ]

    for pattern in patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            candidate = match.group(1).strip(" ?!,'\"")  # strip trailing punctuation and quotes
            # Exact match
            if candidate in titles_lower:
                return all_titles[titles_lower.index(candidate)]
            # Fuzzy match fallback
            matches = difflib.get_close_matches(candidate, titles_lower, n=1, cutoff=cutoff)
            if matches:
                return all_titles[titles_lower.index(matches[0])]
    return None

def get_author_by_title(title):
    book_result = supabase.from_("books").select("book_id, title").ilike("title", f"%{title}%").execute()
    books = book_result.data
    if not books:
        return None
    book_id = books[0]['book_id']

    author_links_result = supabase.from_("book_authors").select("author_id").eq("book_id", book_id).execute()
    author_links = author_links_result.data
    if not author_links:
        return None

    author_names = []
    for link in author_links:
        author_id = link['author_id']
        author_result = supabase.from_("authors").select("name").eq("author_id", author_id).execute()
        authors = author_result.data
        if authors:
            author_names.append(authors[0]['name'])
    return ', '.join(author_names) if author_names else None

def get_book_by_title(title):
    result = supabase.from_("books").select("*").ilike("title", f"%{title}%").execute()
    books = result.data
    return books[0] if books else None

def get_book_availability(book_id):
    result = supabase.from_("books").select("available_copies").eq("book_id", book_id).execute()
    data = result.data
    if not data:
        return None
    return int(data[0]['available_copies']) > 0

def process_database_queries(prompt):
    #print(f"Processing DB queries for prompt: {prompt}")  # DEBUG
    
    book_rows = supabase.from_("books").select("title").execute().data
    all_titles = [row['title'] for row in book_rows] if book_rows else []
    #print(f"Available book titles in DB: {all_titles}")  # DEBUG

    title = fuzzy_match_title(prompt, all_titles)
    #print(f"Fuzzy matched title: {title}")  # DEBUG
    if not title:
        print("No matching title found.")
        return None

    # Map keywords to lists of detection phrases
    keywords = {
        "author": ["author", "write", "writer"],
        "isbn": ["isbn", "book number", "book no", "identification"],
        "year": ["year", "publish", "publised", "published"],
        "description": ["tell me about", "description", "information about", "info about", "summary", "details", "give me"],
        "availability": ["available", "availability", "stock", "in stock", "have"]
    }

    lower_prompt = prompt.lower()
    found_keyword = None
    # Detect keywords by checking if any phrase is contained (not just fuzzy single word matches)
    for key, phrases in keywords.items():
        for phrase in phrases:
            if phrase in lower_prompt:
                found_keyword = key
                #print(f"Detected keyword '{found_keyword}' by phrase '{phrase}'")  # DEBUG
                break
        if found_keyword:
            break

    if found_keyword == "author":
        author = get_author_by_title(title)
        return f"The author of '{title}' is {author}." if author else f"Sorry, author for '{title}' not found."
    if found_keyword == "isbn":
        book = get_book_by_title(title)
        return f"The ISBN of '{book['title']}' is {book['isbn']}." if book and book.get("isbn") else f"Sorry, ISBN not found for '{title}'."
    if found_keyword == "year":
        book = get_book_by_title(title)
        return f"'{book['title']}' was published in {book['publication_year']}." if book and book.get("publication_year") else f"Sorry, publication year not found for '{title}'."
    if found_keyword == "description":
        book = get_book_by_title(title)
        return f"{book['title']}: {book['description']}" if book and book.get("description") else f"Sorry, description not found for '{title}'."
    if found_keyword == "availability":
        book = get_book_by_title(title)
        if book:
            available = get_book_availability(book['book_id'])
            #print(f"Book availability for '{title}': {available}")  # DEBUG
            return f"Yes, '{book['title']}' is available." if available else f"No, '{book['title']}' is not currently available."
        else:
            return f"Sorry, I could not find '{title}'."
    print("No recognized keyword found.")
    return None

def is_library_keyword(prompt: str, keywords):
    words = prompt.lower().split()
    for w in words:
        close_matches = difflib.get_close_matches(w, keywords, n=1, cutoff=0.8)
        if close_matches:
            return True
    return False

def interactive_loop():
    total_tokens = 0
    print("📚 LibraryBot w/ token + Supabase. Type '/bye' to exit.")
    greeting_pattern = re.compile(
        r'\b(?:hi|hello|hey|good morning|good afternoon|good evening)\b', re.IGNORECASE
    )

    keywords = [
    "book", "author", "isbn", "catalog", "borrow",
    "library", "reading", "reference", "return",
    "reserve", "renew", "fine", "due date", "shelf",
    "card", "dashboard",
    "year", "available", "availability", "description, isbn"
    ]


    local_responses = {
        "borrow": "Borrowing is a process where you give or lend a book to someone else. It's usually for a certain period (often 14 days).",
        "fine": "The fine is due on [due date]. You can check your account or contact the library for more information.",
        "return": "Returning a book means giving it back to the library. Make sure to return it by the due date to avoid fines.",
        "reserve": "Reserving a book allows you to hold a copy so you can borrow it later when available.",
        "renew": "Renewing a book extends the borrowing period, usually online or at the library."
    }

    followup_triggers = [
        "more information", "more info", "shorter", "explain", "details",
        "also", "tell me", "what about", "give me", "i want to know"
    ]

    last_library_topic = None

    while True:
        prompt = input("You: ").strip()
        if not prompt:
            continue
        if prompt.lower() in ["/bye", "exit", "quit"]:
            print("Goodbye!")
            break

        # Database queries first
        response = process_database_queries(prompt)
        if response:
            print("LibraryBot:", response)
            log_entry({
                "ts": datetime.now().isoformat(),
                "prompt": prompt,
                "prompt_tokens": 0,
                "response": response,
                "response_tokens": 0,
                "total_tokens_after": total_tokens,
                "note": "database_query"
            })
            continue

        # Greetings locally
        if greeting_pattern.search(prompt):
            response = "This is LibraX AI — how can I help you today?"
            print("LibraryBot:", response)
            log_entry({
                "ts": datetime.now().isoformat(),
                "prompt": prompt,
                "prompt_tokens": 0,
                "response": response,
                "response_tokens": 0,
                "total_tokens_after": total_tokens,
                "note": "greeting_detected"
            })
            continue

        # Local shortcut responses
        matched_local = False
        for key in local_responses:
            if key in prompt.lower():
                response = local_responses[key]
                last_library_topic = key
                print("LibraryBot:", response)
                log_entry({
                    "ts": datetime.now().isoformat(),
                    "prompt": prompt,
                    "prompt_tokens": 0,
                    "response": response,
                    "response_tokens": 0,
                    "total_tokens_after": total_tokens,
                    "note": f"local_response_{key}"
                })
                matched_local = True
                break
        if matched_local:
            continue

        # Followup and LLM request
        is_followup = any(trigger in prompt.lower() for trigger in followup_triggers)
        if is_library_keyword(prompt, keywords):
            last_library_topic = prompt
            prompt_to_send = prompt
        elif is_followup and last_library_topic:
            prompt_to_send = last_library_topic + " " + prompt
            last_library_topic = prompt_to_send
        else:
            response = "Sorry, I can only help with library-related inquiries."
            print("LibraryBot:", response)
            log_entry({
                "ts": datetime.now().isoformat(),
                "prompt": prompt,
                "prompt_tokens": 0,
                "response": response,
                "response_tokens": 0,
                "total_tokens_after": total_tokens,
                "note": "filtered_locally"
            })
            continue

        prompt_tokens = count_tokens(prompt_to_send)
        response = call_library_bot(prompt_to_send)
        response_tokens = count_tokens(response)
        total_tokens += prompt_tokens + response_tokens

        print("LibraryBot:", response)
        print(f"[tokens] prompt: {prompt_tokens}  response: {response_tokens}  session total: {total_tokens}")

        log_entry({
            "ts": datetime.now().isoformat(),
            "prompt": prompt_to_send,
            "prompt_tokens": prompt_tokens,
            "response": response,
            "response_tokens": response_tokens,
            "total_tokens_after": total_tokens
        })

if __name__ == "__main__":
    interactive_loop()
