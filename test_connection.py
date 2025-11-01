from supabase import create_client, Client

SUPABASE_URL = "https://muddfgkpzvfdhljkeprn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im11ZGRmZ2twenZmZGhsamtlcHJuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEyMjYzODcsImV4cCI6MjA3NjgwMjM4N30.g7a_QcoAcbsGLvYkylsLW52-PfhuHwmERKrBCkbpErI"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def print_books():
    response = supabase.from_("books").select("title").execute()
    print("Books fetched:", response.data)

print_books()