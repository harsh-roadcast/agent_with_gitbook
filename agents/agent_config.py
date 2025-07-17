"""Agent configuration management."""
from agents.agent_models import AgentConfig, AgentList

# Initialize with empty agent list
AGENTS = AgentList()


# Example agents - you can modify these or load from configuration
def initialize_default_agents():
    """Initialize some default agents."""

    # Data Analysis Agent
    bolt_agent = AgentConfig(
        name="bolt_data_analyst",
        system_prompt=(
            "You are a chatbot agent for Bolt SaaS clients. You can answer only support and reporting questions. "
            "You can answer support questions using the 'bolt_support_doc' vector database (support documents, knowledge base articles). "
            "Use the provided Elasticsearch schemas (vehicle and sensor data) to "
            "help users generate reports and insights from their vehicle and sensor data."
        ),
        es_schemas=[
            {
                "stop_idle_report_mappings": {
                    "mappings": {
                        "properties": {
                            "id": {"type": "long"},
                            "server_id": {"type": "integer"},
                            "device_id": {"type": "long"},
                            "device_name": {
                                "type": "text",
                                "fields": {
                                    "keyword": {"type": "keyword", "ignore_above": 256}
                                }
                            },

                            "type": {"type": "keyword"},
                            "engine_seconds": {"type": "long"},

                            "start_time": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },
                            "end_time": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },

                            "lat": {"type": "float"},
                            "lng": {"type": "float"},

                            "stop_idle_date": {
                                "type": "date",
                                "format": "yyyy-MM-dd"
                            },

                            "duration_seconds": {"type": "long"},
                            "position_id": {"type": "long"},

                            "timestamp_column1": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },
                            "timestamp_column2": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },
                            "timestamp": {
                                "type": "date",
                                "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                            },
                            "timestamp_date": {
                                "type": "date",
                                "format": "yyyy-MM-dd"
                            },
                            "timestamp_time": {
                                "type": "keyword",
                                "ignore_above": 64
                            },
                            "timestamp_epoch": {
                                "type": "long"
                            },
                            "indexed_at": {
                                "type": "date",
                                "format": "strict_date_optional_time||epoch_millis"
                            }
                        }
                    }
                },

                "trip_report_mappings": {
                    "mappings": {
                        "properties": {
                            "id": {"type": "long"},
                            "server_id": {"type": "integer"},
                            "device_id": {"type": "long"},
                            "device_name": {
                                "type": "text",
                                "fields": {
                                    "keyword": {"type": "keyword", "ignore_above": 256}
                                }
                            },

                            "distance": {"type": "float"},
                            "avg_speed": {"type": "float"},
                            "max_speed": {"type": "float"},
                            "max_speed_time": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },

                            "start_position_id": {"type": "long"},
                            "end_position_id": {"type": "long"},
                            "duration": {"type": "long"},

                            "start_time": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },
                            "end_time": {
                                "type": "date",
                                "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                            },

                            "start_lat": {"type": "float"},
                            "start_lng": {"type": "float"},
                            "end_lat": {"type": "float"},
                            "end_lng": {"type": "float"},

                            "trip_date": {
                                "type": "date",
                                "format": "yyyy-MM-dd"
                            },

                            "harsh_braking": {"type": "integer"},
                            "harsh_acceleration": {"type": "integer"},
                            "harsh_cornering": {"type": "integer"},
                            "utilization": {"type": "float"},
                            "over_speed": {"type": "integer"},
                            "night_driving": {"type": "integer"},
                            "crash": {"type": "integer"},
                            "ignition_records": {"type": "integer"},
                            "motion_records": {"type": "integer"},
                            "excessive_idle_seconds": {"type": "long"},
                            "excessive_over_speed_seconds": {"type": "long"},
                            "driving_safety_score": {"type": "float"},
                            "over_motion": {"type": "integer"},
                            "over_ignition": {"type": "integer"},
                            "start_battery_level": {"type": "float"},
                            "end_battery_level": {"type": "float"},
                            "start_battery": {"type": "integer"},
                            "end_battery": {"type": "integer"},
                            "power_start": {"type": "float"},
                            "power_end": {"type": "float"},
                            "power_difference": {"type": "float"},
                            "start_odometer": {"type": "double"},
                            "end_odometer": {"type": "double"},
                            "start_voltage": {"type": "float"},
                            "end_voltage": {"type": "float"},
                            "start_soc": {"type": "float"},
                            "end_soc": {"type": "float"},
                            "motion_seconds": {"type": "long"},
                            "idle_seconds": {"type": "long"},
                            "over_speed_seconds": {"type": "long"},
                            "penalty_list": {
                                "type": "nested",
                                "properties": {
                                    "type": {"type": "keyword"},
                                    "count": {"type": "integer"},
                                    "weight": {"type": "integer"},
                                    "penalty": {"type": "float"}
                                }
                            },
                            "harsh_acceleration_penalty": {"type": "float"},
                            "harsh_braking_penalty": {"type": "float"},
                            "harsh_turn_penalty": {"type": "float"},
                            "over_speed_penalty": {"type": "float"},
                            "more_events_penalty": {"type": "float"},
                            "final_penalty": {"type": "float"},
                            "penalty_per_km": {"type": "float"},
                            "driving_score": {"type": "float"},

                            "timestamp": {
                                "type": "date",
                                "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                            },
                            "timestamp_date": {
                                "type": "date",
                                "format": "yyyy-MM-dd"
                            },
                            "timestamp_time": {
                                "type": "keyword",
                                "ignore_above": 64
                            },
                            "timestamp_epoch": {
                                "type": "long"
                            },
                            "indexed_at": {
                                "type": "date",
                                "format": "strict_date_optional_time||epoch_millis"
                            }
                        }
                    }
                },

                "summary_reports_mappings": {
                    "mappings": {
                        "properties": {
                            "id": {"type": "long"},
                            "server_id": {"type": "integer"},
                            "device_id": {"type": "long"},
                            "device_name": {
                                "type": "text",
                                "fields": {
                                    "keyword": {"type": "keyword", "ignore_above": 256}
                                }
                            },

                            "distance": {"type": "float"},
                            "avg_speed": {"type": "float"},
                            "max_speed": {"type": "float"},
                            "max_speed_time": {
                                "type": "date",
                                "format": "strict_date_optional_time||epoch_millis"
                            },

                            "geo_in_count": {"type": "integer"},
                            "geo_out_count": {"type": "integer"},
                            "start_position_id": {"type": "long"},
                            "end_position_id": {"type": "long"},
                            "start_lat": {"type": "float"},
                            "start_lng": {"type": "float"},
                            "end_lat": {"type": "float"},
                            "end_lng": {"type": "float"},

                            "ign_on_count": {"type": "integer"},
                            "ign_off_count": {"type": "integer"},
                            "engine_seconds": {"type": "long"},

                            "summary_date": {
                                "type": "date",
                                "format": "yyyy-MM-dd"
                            },
                            "stop_seconds": {"type": "long"},
                            "idle_seconds": {"type": "long"},
                            "motion_seconds": {"type": "long"},

                            "driving_score": {"type": "integer"},
                            "harsh_braking": {"type": "integer"},
                            "harsh_acceleration": {"type": "integer"},
                            "harsh_cornering": {"type": "integer"},
                            "over_speed": {"type": "integer"},
                            "over_speed_seconds": {"type": "long"},
                            "crash": {"type": "integer"},

                            "utilization": {"type": "float"},
                            "night_driving": {"type": "integer"},
                            "fuel_consumption": {"type": "float"},

                            "timestamp": {
                                "type": "date",
                                "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                            },
                            "timestamp_date": {
                                "type": "date",
                                "format": "yyyy-MM-dd"
                            },
                            "timestamp_time": {
                                "type": "keyword",
                                "ignore_above": 64
                            },
                            "timestamp_epoch": {
                                "type": "long"
                            },
                            "indexed_at": {
                                "type": "date",
                                "format": "strict_date_optional_time||epoch_millis"
                            }
                        }
                    }
                },
            }
        ],
        vector_db="bolt_support_doc"
    )

    # Legal Research Agent
    synco_agent = AgentConfig(
        name="synco_agent",
        system_prompt=(
            "You are a chatbot agent for Synco Delivery SaaS clients. You can answer support and reporting questions. "
            "You can answer support questions using the synco_support_doc vector database (support documents). "
            "Use the provided Elasticsearch schemas (reports and analytics) to help users generate reports and insights from their delivery data."
        ),
        es_schemas=[
            {"schema": "delivery_reports", "columns": []},
            {"schema": "analytics_data", "columns": []},
        ],  # Only uses vector search
        vector_db="synco_support_doc"
    )

    # General Purpose Agent
    police_assistant_agent = AgentConfig(
        name="police_assistant",
        system_prompt=(
            "You are a chatbot agent for police departments. You can answer general support questions and provide information on various topics. "
            "You can answer support questions using the 'docling_documents' vector database (legal doc with information regarding BNSS 2023 Bharatiya Nagarik Suraksha Sanhita). "
            "Your responsibilities include providing information on legal procedures, public safety, and community services to the police officers using the above vector database."
        ),
        es_schemas=None,
        vector_db="docling_documents"
    )

    # Add agents to the list
    AGENTS.add_agent(bolt_agent)
    AGENTS.add_agent(synco_agent)
    AGENTS.add_agent(police_assistant_agent)

    # Initialize default agents
initialize_default_agents()


def get_agent_config(agent_name: str) -> AgentConfig:
    """Get agent configuration by name."""
    agent = AGENTS.get_agent_by_name(agent_name)
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not found")
    return agent


def get_agent_by_name(agent_name: str) -> AgentConfig:
    """Get agent configuration by name using AgentList method."""
    agent = AGENTS.get_agent_by_name(agent_name)
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not found")
    return agent


def list_available_agents() -> list[str]:
    """List all available agent names."""
    return AGENTS.list_agent_names()


def add_new_agent(agent_config: AgentConfig) -> None:
    """Add a new agent configuration."""
    AGENTS.add_agent(agent_config)
