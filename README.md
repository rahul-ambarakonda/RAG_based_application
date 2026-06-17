# Discovery Spark ⚡
### Electrical Component RAG-Based Product Discovery Agent

Discovery Spark is a premium, full-stack Retrieval-Augmented Generation (RAG) web application designed to act as an intelligent customer product discovery agent. It helps customers find the exact electrical components (e.g. circuit breakers, contactors, overloads, and switches) from high-volume catalog manuals and brochures.

---

## 🚀 Key Features

* **ChatGPT-Style Conversational UI**: Interactive conversation log that guides customers by asking clarifying follow-up questions (e.g., current rating, voltage, poles, installation style).
* **Dynamic Top 3 Recommendations**: Real-time sidebar updating with the top 3 matching products, part numbers, exact technical specs, match reasons, and page-level citations from the catalogs.
* **Serverless Vector Storage**: Powered by **LanceDB**, a high-performance open-source vector database that runs entirely in-process and stores data locally without requiring Docker.
* **Dynamic Dimension Detection**: Automatically senses the vector dimensions based on the selected embedding model, avoiding database schema mismatches on model swaps.
* **Multi-Cloud Model Configuration**: Seamless support for both **Google Gemini** (default) and **OpenAI** via `.env` settings.
* **Aesthetic Design**: Premium slate-blue dark mode dashboard styled in Vanilla CSS, utilizing glassmorphic components, micro-animations, suggestions chips, and an indexing progress tracker.

---

## 📂 Project Structure

```
RAG_OpenAI/
├── backend/
│   ├── main.py              # FastAPI server & endpoints
│   ├── agent.py             # Product discovery agent & structured JSON outputs
│   ├── db.py                # LanceDB connection & cloud embedding generator
│   ├── index_pdfs.py        # PDF text parser, chunker, & batch indexing script
│   └── requirements.txt     # Python backend dependencies (including pylance)
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Chat and recommendations layout
│   │   ├── index.css        # Premium styling system (glassmorphic theme)
│   │   └── main.jsx         # React application entry point
│   ├── index.html           # Main HTML with SEO metadata
│   ├── package.json         # Node.js configurations
│   └── vite.config.js       # Vite build configurations
├── PDFs/
│   └── README.md            # Directory for storing raw product catalog PDFs
├── .gitignore               # Root ignore rules (excludes .venv, secrets, node_modules, database)
└── README.md                # This documentation
```

---

## 🛠️ Setup & Installation

### Prerequisites
* **Python**: 3.10 or higher (Tested on Python 3.14.0)
* **Node.js**: 18.x or higher
* **npm**: 8.x or higher

### Step 1: Clone and Configure Environment
1. Copy the template `.env` setup in your root directory:
   ```env
   # Cloud AI Provider: 'openai' or 'gemini'
   AI_PROVIDER=gemini

   # API Keys (Provide the one corresponding to the selected provider)
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here

   # Gemini Model Configurations
   GEMINI_CHAT_MODEL=gemini-2.5-flash
   GEMINI_EMBEDDING_MODEL=gemini-embedding-2

   # OpenAI Model Configurations
   OPENAI_CHAT_MODEL=gpt-4o-mini
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small

   # Vector Database Path
   LANCE_DB_PATH=./.lancedb_data
   ```

### Step 2: Set Up Backend
1. Open a terminal and navigate to the project root.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. Start the FastAPI backend:
   ```bash
   cd backend
   python main.py
   ```
   *The API will run on `http://127.0.0.1:8000`.*

### Step 3: Set Up Frontend
1. Open a second terminal window and navigate to the `frontend` directory.
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Launch the Vite dev server:
   ```bash
   npm run dev
   ```
   *The frontend dashboard will be available at `http://localhost:5173/`.*

---

## 🔍 How to Use

1. Place your electrical component manuals and brochures (in PDF format) into the `PDFs/` folder.
2. Open your browser to `http://localhost:5173/`.
3. If the database is not yet initialized, click **🚀 Start Indexing Product Manuals**. The server will parse all PDFs, generate embeddings, and load them into LanceDB.
4. Once ready, ask the agent for recommendations! E.g.:
   * *"I need a low voltage circuit breaker for a high current rating."*
5. The agent will ask follow-up questions to clarify your specifications (e.g. current rating in Amperes, number of poles, drawout vs. fixed installation).
6. Provide details, and the sidebar will update dynamically to display the **Top 3 Recommended Products** matching those specs, cited straight from your PDF catalogs!
