from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

if HF_API_KEY is None:
    raise ValueError("Hugging Face API key not found. Check your .env file.")