import sys
import os

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from huggingface_hub import InferenceClient
from agent.config import HF_API_KEY

def test_llm():
    client = InferenceClient(api_key=HF_API_KEY)

    try:
        response = client.chat_completion(
            model="HuggingFaceH4/zephyr-7b-beta",
            messages=[
                {"role": "user", "content": "Give 3 bullet points about AI for students"}
            ],
            max_tokens=100
        )

        print("\n✅ LLM Response:\n")
        print(response.choices[0].message["content"])

    except Exception as e:
        print("❌ Error occurred:")
        print(repr(e))

if __name__ == "__main__":
    test_llm()