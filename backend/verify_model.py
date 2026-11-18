"""
Verification script to check which LLM model the application is configured to use.
Run this from the backend directory: python verify_model.py
"""
import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings

print("=" * 60)
print("🔍 MODEL CONFIGURATION VERIFICATION")
print("=" * 60)
print(f"\n✓ OpenAI Base Model:  {settings.openai_model}")
print(f"✓ Q&A Model:          {settings.qa_model}")
print(f"✓ Base URL:           {settings.openai_base_url}")
print(f"✓ Vision Model:       {settings.openai_vision_model or '(disabled)'}")
print(f"\n✓ Embedding Model:    {settings.embedding_model}")
print(f"✓ Reranker Model:     {settings.reranker_model}")
print("\n" + "=" * 60)

# Test connection to Ollama
try:
    from openai import OpenAI
    
    client = OpenAI(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key
    )
    
    print("\n🧪 Testing connection to Ollama...")
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": "Reply with just the word 'Hello'"}],
        max_tokens=10
    )
    
    print(f"✅ Successfully connected to model: {settings.openai_model}")
    print(f"   Model response: {response.choices[0].message.content}")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error connecting to model: {e}")
    print("   Make sure Ollama is running and the model is pulled.")
    print("=" * 60)
