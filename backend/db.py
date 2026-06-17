import os
import lancedb
import pyarrow as pa
from dotenv import load_dotenv
from openai import OpenAI
from google import genai

# Load environment variables
load_dotenv(override=True)


AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
LANCE_DB_PATH = os.getenv("LANCE_DB_PATH", "./.lancedb_data")

# Initialize clients lazily to avoid crashing on import if keys are missing
_openai_client = None
_gemini_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        # The new google-genai library uses genai.Client
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

def get_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text using the configured cloud model.
    """
    # Clean text to prevent errors
    text = text.replace("\n", " ").strip()
    if not text:
        text = "empty"

    if AI_PROVIDER == "openai":
        client = get_openai_client()
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        response = client.embeddings.create(
            input=[text],
            model=model
        )
        return response.data[0].embedding
    elif AI_PROVIDER == "gemini":
        client = get_gemini_client()
        model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
        response = client.models.embed_content(
            model=model,
            contents=text
        )
        return response.embeddings[0].values
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {AI_PROVIDER}")

# Schema for the database
def get_schema(vector_dim: int) -> pa.Schema:
    return pa.schema([
        pa.field("id", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), vector_dim)),
        pa.field("text", pa.string()),
        pa.field("pdf_name", pa.string()),
        pa.field("page_num", pa.int32()),
        pa.field("chunk_id", pa.int32())
    ])

def get_db_connection():
    """
    Connect to LanceDB local storage.
    """
    # Create the directory if it doesn't exist
    os.makedirs(LANCE_DB_PATH, exist_ok=True)
    return lancedb.connect(LANCE_DB_PATH)

_embedding_dim = None

def get_embedding_dim() -> int:
    """
    Determine the dimension of the embedding model dynamically.
    """
    global _embedding_dim
    if _embedding_dim is None:
        try:
            vector = get_embedding("dim_check")
            _embedding_dim = len(vector)
            print(f"Detected embedding dimension: {_embedding_dim}")
        except Exception as e:
            print(f"Error determining embedding dimension: {e}. Using fallback defaults.")
            _embedding_dim = 1536 if AI_PROVIDER == "openai" else 3072
    return _embedding_dim

def get_table():
    """
    Open or create the table in LanceDB.
    """
    db = get_db_connection()
    table_name = "pdf_chunks"

    if table_name in db.table_names():
        return db.open_table(table_name)
    else:
        vector_dim = get_embedding_dim()
        schema = get_schema(vector_dim)
        return db.create_table(table_name, schema=schema)

def search_chunks(query: str, limit: int = 5) -> list[dict]:
    """
    Perform vector search on the table.
    """
    try:
        table = get_table()
    except Exception as e:
        print(f"Error opening table: {e}. Has the PDF indexer run?")
        return []

    try:
        query_vector = get_embedding(query)
        # Search the database
        results = table.search(query_vector).limit(limit).to_list()
        
        output = []
        for res in results:
            output.append({
                "text": res["text"],
                "pdf_name": res["pdf_name"],
                "page_num": res["page_num"],
                "score": res.get("_distance", 1.0)  # L2 distance
            })
        return output
    except Exception as e:
        print(f"Search failed: {e}")
        return []
