"""Configuration management with validation and environment support."""
import logging
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ElasticsearchConfig:
    """Elasticsearch configuration."""
    host: str
    username: str
    password: str
    verify_certs: bool = False
    request_timeout: int = 30


@dataclass
class ModelConfig:
    """Model configuration for embeddings and LLM."""
    embedding_model: str = 'all-MiniLM-L6-v2'
    openai_api_key: str = ""
    default_chart_type: str = "column"
    default_query_size: int = 10


@dataclass
class AppConfig:
    """Main application configuration."""
    elasticsearch: ElasticsearchConfig
    models: ModelConfig
    es_schema: str
    es_instructions: str
    log_level: str = "INFO"


class ConfigManager:
    """Centralized configuration management."""

    def __init__(self):
        self._config: Optional[AppConfig] = None
        self._llm_initialized = False

    @property
    def config(self) -> AppConfig:
        """Get configuration, loading it if not already loaded."""
        if self._config is None:
            self._config = self._load_config()
            # Initialize LM when config is first accessed
            self._ensure_llm_initialized()
        return self._config

    def _ensure_llm_initialized(self):
        """Ensure DSPy LM is initialized."""
        if not self._llm_initialized:
            try:
                from services.llm_service import init_llm
                # Initialize with a default model name
                init_llm("gpt-4o-mini")
                self._llm_initialized = True
                logger.info("DSPy LM initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize DSPy LM: {e}", exc_info=True)

    def _load_config(self) -> AppConfig:
        """Load configuration from environment variables."""
        elasticsearch_config = ElasticsearchConfig(
            host=os.getenv('ES_HOST', 'https://62.72.41.235:9200'),
            username=os.getenv('ES_USERNAME', 'elastic'),
            password=os.getenv('ES_PASSWORD', 'GGgCYcnpA_0R_fT5TfFY'),
            verify_certs=os.getenv('ES_VERIFY_CERTS', 'False').lower() == 'true',
            request_timeout=int(os.getenv('ES_REQUEST_TIMEOUT', '30'))
        )

        model_config = ModelConfig(
            embedding_model=os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
            openai_api_key=os.getenv('OPENAI_API_KEY', ''),
            default_chart_type=os.getenv('DEFAULT_CHART_TYPE', 'column'),
            default_query_size=int(os.getenv('DEFAULT_QUERY_SIZE', '10'))
        )

        return AppConfig(
            elasticsearch=elasticsearch_config,
            models=model_config,
            es_schema=self._get_es_schema(),
            es_instructions=os.getenv('ES_INSTRUCTIONS', ''),
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )

    def _get_es_schema(self) -> str:
        """Get Elasticsearch schema definition."""
        return """
        INDEX_SCHEMA = {
            "vehicle_summary_llm_chatbot": [
                "avg_speed", "center", "crash", "device_id", "device_name", "distance",
                "driving_safety_score", "driving_score", "end_lat", "end_lng", "end_odometer",
                "end_position_id", "end_time", "end_time_date", "end_time_time", "engine_2_seconds",
                "engine_seconds", "excessive_idle_seconds", "excessive_over_speed_seconds",
                "excessive_stop_seconds", "filter_positions_count", "final_penalty", "first_ignition_on",
                "first_position_time", "front", "frontLeft", "frontRight", "front_right_motor_time",
                "fuel_consumption", "geo_in_count", "geo_in_distance", "geo_in_end", "geo_in_seconds",
                "geo_out_count", "geo_out_distance", "geo_out_seconds", "harsh_acceleration",
                "harsh_acceleration_penalty", "harsh_braking", "harsh_braking_penalty", "harsh_cornering",
                "harsh_turn_penalty", "id", "idle_seconds", "ign_off_count", "ign_on_count",
                "ignition_records", "last_battery", "last_battery_level", "last_ignition_on",
                "last_position_time", "low_batt_counts", "low_fuel_counts", "max_speed",
                "max_speed_time", "more_events_penalty", "motion_records", "motion_seconds",
                "night_driving", "over_ignition", "over_motion", "over_speed", "over_speed_penalty",
                "over_speed_seconds", "penalty_list", "penalty_per_km", "power_cut_counts",
                "raw_positions_count", "server_id", "start_battery", "start_battery_level",
                "start_lat", "start_lng", "start_odometer", "start_position_id", "start_time",
                "start_time_date", "start_time_time", "steps", "stop_seconds", "summary_date",
                "utilization", "timestamp_date", "timestamp_time", "timestamp_epoch",
            ],
            "vehicle_stop_idle_reports": [
                "id", "server_id", "device_id", "device_name", "type", "engine_seconds",
                "start_time", "start_time_date", "start_time_time", "start_time_epoch",
                "end_time", "end_time_date", "end_time_time", "end_time_epoch",
                "lat", "lng", "stop_idle_date", "duration_seconds", "position_id",
                "timestamp_column1", "timestamp_column2", "timestamp_date", "timestamp_time", "timestamp_epoch",
            ],
            "vehicle_alarm_events": [
                "id", "type", "servertime", "servertime_date", "servertime_time", "servertime_epoch",
                "deviceid", "positionid", "geofenceid", "fixtime", "fixtime_date", "fixtime_time", "fixtime_epoch",
                "latitude", "longitude", "geofencename", "driver_id", "tag_id", "status", "alarm", "timestamp_date", 
                "timestamp_time", "timestamp_epoch",
            ],
            "vehicle_trip_summary": [
                "id", "server_id", "device_id", "device_name", "distance", "avg_speed", "max_speed",
                "max_speed_time", "max_speed_time_date", "max_speed_time_time", "max_speed_time_epoch",
                "start_position_id", "end_position_id", "duration", "start_time", "start_time_date",
                "start_time_time", "start_time_epoch", "end_time", "end_time_date", "end_time_time",
                "end_time_epoch", "start_lat", "end_lat", "start_lng", "end_lng", "trip_date", "timestamp_date",
                 "timestamp_time", "timestamp_epoch",
            ]
        }
        """

    def update_config(self, **kwargs) -> None:
        """Update configuration values for testing."""
        if self._config is None:
            self._config = self._load_config()

        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)


# Global configuration manager instance
config_manager = ConfigManager()
