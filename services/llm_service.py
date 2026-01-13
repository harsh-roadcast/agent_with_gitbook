import logging
import os
from pathlib import Path
from typing import Any, Dict

import dspy
from dspy.utils.callback import BaseCallback


from core.config import config_manager
import mlflow
logger = logging.getLogger(__name__)


def init_llm():
    """Initialize the DSPy language model without usage tracking"""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        project_root = Path(__file__).resolve().parent.parent
        tracking_dir = project_root / "mlruns"
        tracking_dir.mkdir(parents=True, exist_ok=True)
        tracking_uri = f"file:{tracking_dir.as_posix()}"
        logger.info(f"MLFLOW_TRACKING_URI not set; defaulting to {tracking_uri}")

    mlflow.set_tracking_uri(tracking_uri)
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
    mlflow.set_tag("runName", session_id)
    mlflow.set_tag("source", message_id)