import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)
