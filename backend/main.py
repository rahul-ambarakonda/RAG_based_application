import os
import sys
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_db_connection, AI_PROVIDER, LANCE_DB_PATH
from agent import run_agent, AgentResponse
from index_pdfs import index_all_pdfs

load_dotenv(override=True)

app = FastAPI(title="RAG Product Discovery Agent API")

# Add CORS middleware to support Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

# Globals to track indexing state
is_indexing_in_progress = False

@app.get("/api/status")
def get_status():
    """
    Get backend status, vector DB count, and current provider config.
    """
    global is_indexing_in_progress
    
    db_exists = False
    num_chunks = 0
    
    try:
        db = get_db_connection()
        table_name = "pdf_chunks"
        if table_name in db.table_names():
            table = db.open_table(table_name)
            db_exists = True
            num_chunks = len(table.to_pandas())
    except Exception as e:
        print(f"Error checking database status: {e}")
        
    return {
        "provider": AI_PROVIDER,
        "chat_model": os.getenv("OPENAI_CHAT_MODEL" if AI_PROVIDER == "openai" else "GEMINI_CHAT_MODEL"),
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL" if AI_PROVIDER == "openai" else "GEMINI_EMBEDDING_MODEL"),
        "db_indexed": db_exists and num_chunks > 0,
        "num_chunks": num_chunks,
        "indexing_in_progress": is_indexing_in_progress,
        "database_path": LANCE_DB_PATH
    }

def background_indexing_task():
    global is_indexing_in_progress
    try:
        index_all_pdfs()
    except Exception as e:
        print(f"Background indexing task failed: {e}")
    finally:
        is_indexing_in_progress = False

@app.post("/api/index")
def trigger_index(background_tasks: BackgroundTasks):
    """
    Asynchronously trigger the PDF indexing process.
    """
    global is_indexing_in_progress
    if is_indexing_in_progress:
        return {"message": "Indexing is already in progress.", "status": "running"}
        
    is_indexing_in_progress = True
    background_tasks.add_task(background_indexing_task)
    return {"message": "Indexing started in the background.", "status": "started"}

@app.post("/api/chat", response_model=AgentResponse)
def chat_endpoint(request: ChatRequest):
    """
    Accept user messages history, run semantic search and the AI agent,
    and return the conversational text + top 3 products.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty.")
        
    # Get last message as current query
    last_msg = request.messages[-1]
    if last_msg.role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user.")
        
    user_message = last_msg.content
    
    # Format history (all messages except the last one)
    history = []
    for msg in request.messages[:-1]:
        history.append({
            "role": "user" if msg.role == "user" else "assistant",
            "content": msg.content
        })
        
    # Run the agent
    response = run_agent(history, user_message)
    return response

@app.get("/")
def read_root():
    return {"message": "Welcome to RAG Product Discovery Agent API. Access /docs for API documentation."}

if __name__ == "__main__":
    import uvicorn
    # Start the server on port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
