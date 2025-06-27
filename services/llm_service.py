import logging

import dspy

from core.config import config_manager

# Configure logging
logger = logging.getLogger(__name__)


def init_llm(model_name: str):
    """Initialize the DSPy language model without usage tracking"""
    try:
        # Get the OpenAI API key from the new configuration system
        api_key = config_manager.config.models.openai_api_key

        if not api_key:
            logger.warning("No OpenAI API key found in configuration")
            return None

        local_llm = dspy.LM(model='openai/gpt-4.1-mini', api_key=api_key)
        dspy.settings.configure(lm=local_llm)
        #TODO: Configure custom cache using redis
        dspy.configure_cache(enable_disk_cache=True, enable_memory_cache=True)
        logger.info(f"Successfully configured DSPy with OpenAI model: {model_name}")
        return local_llm
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI LLM: {e}", exc_info=True)
        return None
