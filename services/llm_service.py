import logging
import os
from typing import Any, Dict

import dspy
from dspy.utils.callback import BaseCallback


from core.config import config_manager

# Make MLflow optional
MLFLOW_ENABLED = os.getenv("MLFLOW_ENABLED", "false").lower() == "true"
if MLFLOW_ENABLED:
    try:
        import mlflow
    except ImportError:
        MLFLOW_ENABLED = False
        mlflow = None
else:
    mlflow = None

logger = logging.getLogger(__name__)


def init_llm():
    """Initialize the DSPy language model without usage tracking"""
    if MLFLOW_ENABLED and mlflow:
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
        # Create a unique name for your experiment.
        mlflow.set_experiment("DSPy-rsdc")
        mlflow.dspy.autolog(log_traces_from_eval=True)

    api_key = config_manager.config.models.openai_api_key

    local_llm = dspy.LM(model='openai/gpt-4.1-mini', api_key=api_key)
    dspy.settings.configure(lm=local_llm)
    #TODO: Configure custom cache using redis
    dspy.configure_cache(enable_disk_cache=True, enable_memory_cache=True)
    # dspy.configure(callbacks=[AgentLoggingCallback()])
    logger.info(f"Successfully configured DSPy with OpenAI model: {local_llm.model}")
    return local_llm

def set_mlflow_trace_name(session_id: str, message_id: str):
    """Set the MLflow trace name for the current trace."""
    if MLFLOW_ENABLED and mlflow:
        mlflow.set_tag("runName", session_id)
        mlflow.set_tag("source", message_id)