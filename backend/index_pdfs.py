import os
import sys
import uuid
from pypdf import PdfReader
from tqdm import tqdm
from dotenv import load_dotenv

# Add backend directory to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_db_connection, get_table, get_embedding, get_schema, AI_PROVIDER, get_embedding_dim

# Configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 50

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    if not text:
        return chunks
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]
    
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        # Move start by (chunk_size - overlap)
        start += (chunk_size - chunk_overlap)
        
        # If the next chunk would be extremely small, we can stop
        if start >= len(text) - chunk_overlap:
            break
            
    return chunks

def extract_pdf_data(pdf_path: str) -> list[dict]:
    """
    Extracts pages and chunks from a single PDF.
    """
    pdf_name = os.path.basename(pdf_path)
    print(f"\nParsing {pdf_name}...")
    
    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return []

    num_pages = len(reader.pages)
    print(f"Found {num_pages} pages.")
    
    chunks_data = []
    chunk_index = 0
    
    for page_idx in tqdm(range(num_pages), desc=f"Processing {pdf_name}"):
        page = reader.pages[page_idx]
        try:
            page_text = page.extract_text()
        except Exception as e:
            print(f"Error extracting text from page {page_idx + 1} of {pdf_name}: {e}")
            continue
            
        if not page_text or not page_text.strip():
            continue
            
        page_chunks = chunk_text(page_text)
        
        for chunk in page_chunks:
            chunks_data.append({
                "text": chunk,
                "pdf_name": pdf_name,
                "page_num": page_idx + 1,
                "chunk_id": chunk_index
            })
            chunk_index += 1
            
    return chunks_data

def index_all_pdfs():
    """
    Main pipeline: read PDFs, generate embeddings in batches, and save to LanceDB.
    """
    # 1. Locate PDF directory
    # Assume script is run from project root or backend folder
    pdf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "PDFs"))
    if not os.path.exists(pdf_dir):
        print(f"PDF directory not found at: {pdf_dir}")
        return
        
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        return
        
    print(f"Found {len(pdf_files)} PDFs: {pdf_files}")
    print(f"Using Cloud Embeddings Provider: {AI_PROVIDER}")
    
    # 2. Extract text and create all chunks
    all_chunks = []
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        all_chunks.extend(extract_pdf_data(pdf_path))
        
    total_chunks = len(all_chunks)
    print(f"\nTotal chunks generated: {total_chunks}")
    if total_chunks == 0:
        print("No chunks to index.")
        return

    # 3. Create or clear the LanceDB table
    print("\nPreparing LanceDB Table...")
    db = get_db_connection()
    table_name = "pdf_chunks"
    
    # Remove existing table to avoid duplicates on re-index
    if table_name in db.table_names():
        print(f"Deleting existing table '{table_name}' for clean rebuild...")
        db.drop_table(table_name)
        
    vector_dim = get_embedding_dim()
    schema = get_schema(vector_dim)
    table = db.create_table(table_name, schema=schema)
    
    # 4. Generate embeddings and upload in batches
    print(f"\nGenerating embeddings in batches of {BATCH_SIZE}...")
    
    rows_to_insert = []
    
    for i in tqdm(range(0, total_chunks, BATCH_SIZE), desc="Generating Embeddings"):
        batch = all_chunks[i:i+BATCH_SIZE]
        
        # Collect texts for batch embedding
        texts = [item["text"] for item in batch]
        
        try:
            # We fetch embeddings for the batch
            embeddings = []
            if AI_PROVIDER == "openai":
                from db import get_openai_client
                client = get_openai_client()
                model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
                response = client.embeddings.create(input=texts, model=model)
                embeddings = [item.embedding for item in response.data]
            else: # gemini
                from db import get_gemini_client
                client = get_gemini_client()
                model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
                # For gemini, we can call embed_content.
                # In google-genai, embed_content supports passing a list of contents.
                response = client.models.embed_content(
                    model=model,
                    contents=texts
                )
                embeddings = [emb.values for emb in response.embeddings]
                
            # Zip embeddings back with metadata
            for idx, item in enumerate(batch):
                rows_to_insert.append({
                    "id": str(uuid.uuid4()),
                    "vector": embeddings[idx],
                    "text": item["text"],
                    "pdf_name": item["pdf_name"],
                    "page_num": item["page_num"],
                    "chunk_id": item["chunk_id"]
                })
                
        except Exception as e:
            print(f"\nError generating embeddings for batch {i} to {i+len(batch)}: {e}")
            print("Skipping this batch...")
            continue
            
    # 5. Insert rows into LanceDB
    if rows_to_insert:
        print(f"\nInserting {len(rows_to_insert)} records into LanceDB...")
        table.add(rows_to_insert)
        print("Indexing completed successfully!")
    else:
        print("No records were indexed due to embedding generation failures.")

if __name__ == "__main__":
    # Ensure there is an API key configured before running
    # This is a basic check.
    load_dotenv(override=True)
    if AI_PROVIDER == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("ERROR: AI_PROVIDER is set to 'openai' but OPENAI_API_KEY is not defined in .env")
        sys.exit(1)
    elif AI_PROVIDER == "gemini" and not os.getenv("GEMINI_API_KEY"):
        print("ERROR: AI_PROVIDER is set to 'gemini' but GEMINI_API_KEY is not defined in .env")
        sys.exit(1)
        
    index_all_pdfs()
