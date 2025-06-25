import logging
import dspy
import requests
from dspy import track_usage

from config import settings

# Configure logging
logger = logging.getLogger(__name__)


def init_llm(model_name: str):
    """Initialize the DSPy language model without usage tracking"""
    try:
        local_llm = dspy.LM(model='openai/gpt-4o-mini', api_key=settings.OPENAI_API_KEY)
        dspy.settings.configure(lm=local_llm)
        #TODO: Configure custom cache using redis
        dspy.configure_cache(enable_disk_cache=False, enable_memory_cache=False)
        logger.info(f"Successfully configured DSPy with Ollama model: {model_name}")
        return local_llm
    except Exception as e:
        logger.error(f"Failed to initialize Ollama LLM: {e}", exc_info=True)
        return None
