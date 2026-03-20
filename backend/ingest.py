"""
ingest.py
─────────
Questo file gestisce:
1. Caricamento e parsing di PDF
2. Chunking del testo in segmenti
3. Creazione embeddings con Gemini
4. Salvataggio in ChromaDB

Esecuzione: python ingest.py
"""

import os
from pathlib import Path
import google.generativeai as genai
from pypdf import PdfReader
import chromadb
from dotenv import load_dotenv

# ────────────────────────────────────────
# 1. CONFIGURAZIONE INIZIALE
# ────────────────────────────────────────

from pathlib import Path
import os
from dotenv import load_dotenv
import chromadb
import google.generativeai as genai

BASE_DIR = Path(__file__).resolve().parent  # cartella backend/

# Carica backend/.env in modo esplicito
load_dotenv(dotenv_path=BASE_DIR / ".env")  # load_dotenv accetta anche un Path. [web:756][web:751]

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY non trovata: mettila in backend/.env")

genai.configure(api_key=API_KEY)

# Cartelle (ASSOLUTE e stabili)
PDF_FOLDER = BASE_DIR / "pdfs"
CHROMA_DB_PATH = BASE_DIR / "chroma_db"

# Crea cartelle se non esistono
PDF_FOLDER.mkdir(exist_ok=True)
CHROMA_DB_PATH.mkdir(exist_ok=True)

# Inizializza ChromaDB (persistente su disco) - client
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))  # directory locale di persistenza. [web:735]

# (Opzionale ma utile) log per verificare
print("PDF_FOLDER =", PDF_FOLDER)
print("CHROMA_DB_PATH =", CHROMA_DB_PATH)



# ────────────────────────────────────────
# 2. ESTRAZIONE TESTO DA PDF
# ────────────────────────────────────────

import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text += f"\n--- Pagina {page_num + 1} ---\n"
        text += page.get_text()
    doc.close()
    return text


# ────────────────────────────────────────
# 3. CHUNKING DEL TESTO
# ────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 300) -> list:
    """
    Chunk size più grande + overlap per contesto migliore.
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Taglia a frase/sentenza più vicina (migliora coerenza)
        last_period = chunk.rfind('.')
        if last_period > chunk_size * 0.8:
            end = last_period + 1
            
        chunks.append(chunk.strip())
        start += chunk_size - overlap
    
    print(f"✂️ Testo diviso in {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
    return chunks


# ────────────────────────────────────────
# 4. CREAZIONE EMBEDDINGS (Gemini)
# ────────────────────────────────────────

def get_embeddings(text: str) -> list:
    """
    Crea embedding usando Gemini (GRATUITO con AI Pro).
    
    WHY?
    - Embedding = vettore numerico che rappresenta il significato
    - Permette ricerca semantica (non solo keyword matching)
    - Gemini: incluso con AI Pro, nessun costo aggiuntivo
    
    Args:
        text: testo da convertire in embedding
        
    Returns:
        Vettore embedding (lista di float)
    """
    response = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="RETRIEVAL_DOCUMENT"  # Optimizzato per retrieval
    )
    return response["embedding"]

# ────────────────────────────────────────
# 5. INGESTIONE IN CHROMADB
# ────────────────────────────────────────

def ingest_pdfs_to_chromadb():
    collection = chroma_client.get_or_create_collection(
        name="pdf_knowledge_base",
        metadata={"hnsw:space": "cosine"}
    )
    
    pdf_files = list(Path(PDF_FOLDER).glob("*.pdf"))
    
    if not pdf_files:
        print(f"⚠️ Nessun PDF trovato in {PDF_FOLDER}")
        return
    
    print(f"\n🚀 Inizio ingestione {len(pdf_files)} file(s)\n")
    
    for pdf_file in pdf_files:
        print(f"\n{'='*60}")
        print(f"Elaborazione: {pdf_file.name}")
        print(f"{'='*60}")
        
        try:
            text = extract_text_from_pdf(str(pdf_file))
            chunks = chunk_text(text, chunk_size=1200, overlap=300)
            
            for idx, chunk in enumerate(chunks):
                print(f"  Chunk {idx + 1}/{len(chunks)} → Embedding...", end=" ")
                
                embedding = get_embeddings(chunk)
                
                collection.add(
                    ids=[f"{pdf_file.stem}_chunk_{idx}"],
                    documents=[chunk],
                    embeddings=[embedding],
                    metadatas=[{"source": pdf_file.name, "chunk": idx}]
                )
                print("✓")
            
            print(f"✅ {pdf_file.name} completato!")
            
        except Exception as e:
            print(f"❌ Errore elaborando {pdf_file.name}: {e}")
    
    print("\n" + "="*60)
    print("✅ Ingestione completata!")
    print("="*60)


# ────────────────────────────────────────
# 6. ESECUZIONE
# ────────────────────────────────────────

if __name__ == "__main__":
    ingest_pdfs_to_chromadb()
