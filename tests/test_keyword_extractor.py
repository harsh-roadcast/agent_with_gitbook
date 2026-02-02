"""Test keyword extractor functionality."""
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dspy
from modules.keyword_extractor import KeywordExtractor
from services.llm_service import init_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_dspy():
    """Configure DSPy with OpenAI model."""
    print("🔧 Setting up DSPy with OpenAI...")
    
    # Initialize LLM using the standard service
    lm = init_llm()
    
    print(f"✅ DSPy configured with model: {lm.model}\n")

def test_keyword_extraction():
    """Test keyword extraction with various queries."""
    
    test_queries = [
        # English queries
        "How do I authenticate users with JWT tokens in my application?",
        "What is the best way to optimize database queries?",
        "Show me sales data for last quarter",
        
        # Technical queries
        "Configure Docker container networking",
        "Python async await implementation",
        
        # Hinglish queries (should work without manual translation)
        "authentication kaise karu?",
        "database query optimize karna hai",
        
        # Mixed queries
        "How to deploy using Docker aur Kubernetes?",
        
        # Edge cases
        "",
        "   ",
        "a",
    ]
    
    print("="*70)
    print("KEYWORD EXTRACTION TEST")
    print("="*70)
    print()
    
    extractor = KeywordExtractor(max_keywords=10)
    
    for i, query in enumerate(test_queries, 1):
        print(f"Test {i}:")
        print(f"  Query: '{query}'")
        
        try:
            keywords = extractor.extract_keywords(query)
            
            if keywords:
                print(f"  ✅ Extracted {len(keywords)} keywords:")
                for kw in keywords:
                    print(f"     • {kw}")
            else:
                print(f"  ⚠️  No keywords extracted")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()
    
    print("="*70)

def test_max_keywords_limit():
    """Test that max_keywords limit is respected."""
    
    print("="*70)
    print("MAX KEYWORDS LIMIT TEST")
    print("="*70)
    print()
    
    query = "How do I set up authentication, authorization, JWT tokens, OAuth, security, encryption, HTTPS, SSL, certificates, and user management in my application?"
    
    # Test with different limits
    for max_kw in [3, 5, 10]:
        print(f"Testing with max_keywords={max_kw}:")
        extractor = KeywordExtractor(max_keywords=max_kw)
        keywords = extractor.extract_keywords(query)
        
        print(f"  Returned {len(keywords)} keywords (should be ≤ {max_kw})")
        print(f"  Keywords: {keywords}")
        print(f"  ✅ Limit respected: {len(keywords) <= max_kw}")
        print()
    
    print("="*70)

def main():
    """Run all tests."""
    try:
        setup_dspy()
        test_keyword_extraction()
        test_max_keywords_limit()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.error("Test execution failed", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
