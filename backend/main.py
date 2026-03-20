"""
main.py
───────
FastAPI Backend per Chat with PDF
Endpoints:
- POST /chat → Chat con il PDF
- GET /health → Status check

Esecuzione: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import os
from fastapi import FastAPI
from fastapi import HTTPException
import time
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import chromadb
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Global chat sessions (reset al riavvio server)
chat_sessions = {}

def get_chat_session(session_id: str):
    """Restituisce ChatSession o ne crea una nuova"""
    if session_id not in chat_sessions:
        model = genai.GenerativeModel("models/gemini-2.5-pro")
        chat_sessions[session_id] = model.start_chat()
    return chat_sessions[session_id]


# ────────────────────────────────────────
# 1. SETUP FASTAPI & CORS
# ────────────────────────────────────────

app = FastAPI(
    title="Chat with PDF API",
    version="1.0.0",
    description="RAG Backend usando Gemini + ChromaDB"
)

# CORS = Permetti richieste da React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Per dev: accetta da qualsiasi origine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────
# 2. CONFIGURAZIONE GEMINI & CHROMADB
# ────────────────────────────────────────

from pathlib import Path
import os
from dotenv import load_dotenv
import chromadb
import google.generativeai as genai

BASE_DIR = Path(__file__).resolve().parent  # cartella backend/

# carica backend/.env in modo esplicito
load_dotenv(dotenv_path=BASE_DIR / ".env")  # accetta un path al file .env [web:756]

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY non trovata: mettila in backend/.env")

genai.configure(api_key=API_KEY)

# Path fisso (assoluto) alla cartella di persistenza di Chroma
CHROMA_DB_PATH = BASE_DIR / "chroma_db"
CHROMA_DB_PATH.mkdir(exist_ok=True)

# Client persistente (usa SEMPRE lo stesso path)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))  # [web:735]

# (opzionale) debug: verifica dove sta scrivendo/leggendo
print("CHROMA_DB_PATH =", CHROMA_DB_PATH)


# ────────────────────────────────────────
# 3. MODELLI PYDANTIC (Validazione input)
# ────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    context_count: int = 3
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Schema per risposta del backend"""
    answer: str  # Risposta LLM
    sources: list  # File sorgente utilizzati

# ────────────────────────────────────────
# 4. FUNZIONE RETRIEVAL (Ricerca nel vector store)
# ────────────────────────────────────────

def retrieve_context(query: str, top_k: int = 3) -> tuple:
    """
    RAG Retrieval Step:
    1. Converte query in embedding
    2. Cerca i top_k chunks più simili
    3. Ritorna testo + metadata
    
    Args:
        query: domanda dell'utente
        top_k: numero di risultati da ritornare
        
    Returns:
        (context_text, sources_list)
    """
    try:
        # Get collection
        collection = chroma_client.get_collection(name="pdf_knowledge_base")
        
        # Embedding QUERY (non documento!)
        query_embedding = genai.embed_content(
            model="models/embedding-001",
            content=query,
            task_type="RETRIEVAL_QUERY"  # ← CORRETTO per query!
        )["embedding"]
        
        # Ricerca nei vettori simili
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count())  # evita il warning e usa tutto quello che c'è
        )
        
        # Combina i chunks ritornati
        context_parts = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            source = meta.get("source", "sconosciuto")
            context_parts.append(f"[PDF: {source}]\n{doc}\n")
        context_text = "\n\n".join(context_parts)
        
        sources = list(set(
            meta["source"] for meta in results["metadatas"][0]
        ))
        
        return context_text, sources
        
    except Exception as e:
        print(f"❌ Errore retrieval: {e}")
        return "", []

# ────────────────────────────────────────
# 5. FUNZIONE RAG (Generate Response)
# ────────────────────────────────────────
def call_gemini_with_retry(model, prompt: str, max_retries: int = 3) -> str:
    """
    Chiama Gemini e gestisce errori temporanei con retry + backoff.
    - Utile per 500/503 e transient errors.
    - Se è un errore permanente (quota 429/limit 0), fallisce subito.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            resp = model.generate_content(prompt)
            return resp.text

        except Exception as e:
            last_error = e
            msg = str(e).lower()

            # euristica: se è quota/rate limit, di solito non serve retry aggressivo
            if "quota" in msg or "resource_exhausted" in msg or "429" in msg:
                break

            # backoff esponenziale semplice: 1s, 2s, 4s...
            time.sleep(2 ** attempt)

    raise last_error




def generate_response(query: str, context: str) -> str:
    """Prompt specifico RAG per Gemini 2.5 Pro"""
    prompt = f"""Sei un assistente RAG esperto per documenti PDF.

ISTRUZIONI:
1. Usa SOLO il contesto sotto. Non inventare.
2. Cita sempre [PDF: nome.pdf] dopo ogni informazione.
3. Se la risposta non è nel contesto, di' "Non trovo questa informazione nei documenti."
4. Rispondi in italiano, chiaro e conciso.
5. CITAZIONI: scrivi SEMPRE [PDF: nome_esatto] DOPO OGNI informazione, usando il nome preciso dal contesto.

CONTEXTO (fonti multiple):
{context}

DOMANDA: {query}

RISPOSTA:"""

    model = genai.GenerativeModel("models/gemini-2.5-pro")
    return call_gemini_with_retry(model, prompt, max_retries=3)



    


# ────────────────────────────────────────
# 6. ENDPOINTS FastAPI
# ────────────────────────────────────────

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "✅ Backend è online",
        "service": "Chat with PDF API"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principale: riceve query, ritorna risposta
    
    Flow:
    1. Retrieval: cerca chunks simili nel vector store
    2. Generation: passa query + context a Gemini
    3. Ritorna risposta + sources
    """
    
    print(f"\n🔍 Query ricevuta: {request.query} | Session: {request.session_id}")
    
    # Step 1: Retrieval
    context, sources = retrieve_context(
        query=request.query,
        top_k = request.context_count
    )
    
    if not context:
        return ChatResponse(
            answer="⚠️ Nessun documento caricato. Per favore, carica un PDF.",
            sources=[]
        )
    
    # ← QUI CAMBIA: ChatSession invece di generate_response
    chat = get_chat_session(request.session_id or "default")
    
    rag_prompt = f"""CONTEXTO dai documenti:
{context}

DOMANDA: {request.query}"""
    
    try:
        response = chat.send_message(rag_prompt)
        answer = response.text
        
        print(f"📝 Risposta generata")
        print(f"📚 Sources: {sources}\n")
        
        return ChatResponse(
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        print("Gemini generate_content error:", repr(e))
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini non disponibile in questo momento (possibile quota/rate limit o errore temporaneo). "
                f"Dettaglio: {type(e).__name__}: {e}"
            ),
        )


# ────────────────────────────────────────
# 7. RUN SERVER (quando esegui il file)
# ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════╗
    ║     Chat with PDF - Backend Ready      ║
    ║   🚀 http://localhost:8000             ║
    ║   📖 Docs: http://localhost:8000/docs  ║
    ╚════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
