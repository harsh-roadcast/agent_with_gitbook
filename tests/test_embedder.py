import os
from langchain_openai.embeddings import OpenAIEmbeddings
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def list_available_models():
    """List all available models for this API key."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        models = client.models.list()
        
        all_models = [model.id for model in models.data]
        
        # Filter for embedding models
        embedding_models = [
            m for m in all_models 
            if 'embedding' in m.lower() or 'ada' in m.lower()
        ]
        
        print("\n" + "="*70)
        print("AVAILABLE MODELS FOR YOUR API KEY")
        print("="*70)
        print(f"\nTotal models available: {len(all_models)}")
        print(f"\nEmbedding models found: {len(embedding_models)}")
        
        if embedding_models:
            print("\n📊 Embedding Models:")
            for model in sorted(embedding_models):
                print(f"  ✓ {model}")
        else:
            print("\n⚠️  No embedding models found!")
            print("\nAll available models:")
            for model in sorted(all_models)[:20]:  # Show first 20
                print(f"  • {model}")
            if len(all_models) > 20:
                print(f"  ... and {len(all_models) - 20} more")
        
        print("="*70 + "\n")
        return embedding_models
        
    except Exception as exc:
        logger.error("Failed to list models: %s", exc)
        print(f"❌ Error listing models: {exc}")
        return []

def embed_text(text: str, model: str = None):
    """
    Generate embedding for text using specified model.
    
    Args:
        text: Text to embed
        model: Model name (if None, tries to auto-detect)
    """
    if model is None:
        # Try to find an available model
        available = list_available_models()
        if not available:
            raise ValueError("No embedding models available for this API key")
        model = available[0]
        print(f"Using auto-detected model: {model}\n")
    
    try:
        embedder = OpenAIEmbeddings(model=model, api_key=OPENAI_API_KEY)
        embedding = embedder.embed_query(text)
        return embedding, model
    except Exception as exc:
        logger.error("Embedding generation failed with model '%s': %s", model, exc)
        raise exc

def main():
    text = "Sample text for embedding"
    
    print("🔍 Discovering available embedding models...\n")
    available_models = list_available_models()
    
    if not available_models:
        print("❌ No embedding models available. Please check your OpenAI API key permissions.")
        return
    
    print(f"\n📝 Testing embedding generation with text: '{text}'")
    print("-" * 70)
    
    embedding_vector, model_used = embed_text(text)
    
    print(f"✅ Success!")
    print(f"   Model used: {model_used}")
    print(f"   Embedding dimensions: {len(embedding_vector)}")
    print(f"   First 5 values: {embedding_vector[:5]}")
    print(f"   Data type: {type(embedding_vector[0])}")
    print("-" * 70)

if __name__ == "__main__":
    main()
