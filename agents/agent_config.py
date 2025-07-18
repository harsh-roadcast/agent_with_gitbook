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
            "You are an intelligent assistant for Bolt SaaS clients. Your role is to assist with support and reporting-related queries only. "
            "For support questions, refer to the 'bolt_support_doc' vector database, which contains knowledge base articles and help documentation. "
            "For reporting and analytics questions, use the provided Elasticsearch schemas related to vehicle and sensor data to generate accurate insights, summaries, and visualizations. "
            "Never respond to queries outside the support or reporting scope."
        ),
        es_schemas=[
            {
                "index": "summary_reports",
                "mappings": {
                    "properties": {
                        "attributes": {
                            "properties": {
                                "center": {
                                    "type": "long"
                                },
                                "crash": {
                                    "type": "long"
                                },
                                "driving_safety_score": {
                                    "type": "float"
                                },
                                "driving_score": {
                                    "type": "float"
                                },
                                "end_odometer": {
                                    "type": "float"
                                },
                                "engine_2_seconds": {
                                    "type": "long"
                                },
                                "excessive_idle_seconds": {
                                    "type": "long"
                                },
                                "excessive_over_speed_seconds": {
                                    "type": "long"
                                },
                                "excessive_stop_seconds": {
                                    "type": "long"
                                },
                                "filter_positions_count": {
                                    "type": "long"
                                },
                                "final_penalty": {
                                    "type": "float"
                                },
                                "first_ignition_on": {
                                    "type": "date"
                                },
                                "first_position_time": {
                                    "type": "date"
                                },
                                "front": {
                                    "type": "long"
                                },
                                "frontLeft": {
                                    "type": "long"
                                },
                                "frontRight": {
                                    "type": "long"
                                },
                                "front_right_motor_time": {
                                    "type": "long"
                                },
                                "fuel_consumption": {
                                    "type": "long"
                                },
                                "geo_in_distance": {
                                    "type": "long"
                                },
                                "geo_in_end": {
                                    "type": "boolean"
                                },
                                "geo_in_seconds": {
                                    "type": "long"
                                },
                                "geo_out_distance": {
                                    "type": "float"
                                },
                                "geo_out_seconds": {
                                    "type": "long"
                                },
                                "harsh_acceleration": {
                                    "type": "long"
                                },
                                "harsh_acceleration_penalty": {
                                    "type": "long"
                                },
                                "harsh_braking": {
                                    "type": "long"
                                },
                                "harsh_braking_penalty": {
                                    "type": "long"
                                },
                                "harsh_cornering": {
                                    "type": "long"
                                },
                                "harsh_turn_penalty": {
                                    "type": "long"
                                },
                                "idle_report_count": {
                                    "type": "long"
                                },
                                "ignition_records": {
                                    "type": "long"
                                },
                                "last_battery": {
                                    "type": "long"
                                },
                                "last_battery_level": {
                                    "type": "float"
                                },
                                "last_ignition_on": {
                                    "type": "date"
                                },
                                "last_position_time": {
                                    "type": "date"
                                },
                                "low_batt_counts": {
                                    "type": "long"
                                },
                                "low_fuel_counts": {
                                    "type": "long"
                                },
                                "more_events_penalty": {
                                    "type": "long"
                                },
                                "motion_records": {
                                    "type": "long"
                                },
                                "night_driving": {
                                    "type": "long"
                                },
                                "over_ignition": {
                                    "type": "long"
                                },
                                "over_motion": {
                                    "type": "long"
                                },
                                "over_speed": {
                                    "type": "long"
                                },
                                "over_speed_penalty": {
                                    "type": "long"
                                },
                                "over_speed_seconds": {
                                    "type": "long"
                                },
                                "penalty_list": {
                                    "properties": {
                                        "count": {
                                            "type": "long"
                                        },
                                        "penalty": {
                                            "type": "long"
                                        },
                                        "type": {
                                            "type": "text",
                                            "fields": {
                                                "keyword": {
                                                    "type": "keyword",
                                                    "ignore_above": 256
                                                }
                                            }
                                        },
                                        "weight": {
                                            "type": "long"
                                        }
                                    }
                                },
                                "penalty_per_km": {
                                    "type": "float"
                                },
                                "power_cut_counts": {
                                    "type": "long"
                                },
                                "raw_positions_count": {
                                    "type": "long"
                                },
                                "start_battery": {
                                    "type": "long"
                                },
                                "start_battery_level": {
                                    "type": "float"
                                },
                                "start_odometer": {
                                    "type": "float"
                                },
                                "steps": {
                                    "type": "long"
                                },
                                "stop_report_count": {
                                    "type": "long"
                                },
                                "utilization": {
                                    "type": "float"
                                }
                            }
                        },
                        "avg_speed": {
                            "type": "float"
                        },
                        "crash": {
                            "type": "long"
                        },
                        "device_id": {
                            "type": "long"
                        },

                        "distance": {
                            "type": "float"
                        },
                        "driving_safety_score": {
                            "type": "float"
                        },
                        "driving_score": {
                            "type": "integer"
                        },
                        "duration": {
                            "type": "long"
                        },
                        "duration_seconds": {
                            "type": "long"
                        },
                        "end_battery": {
                            "type": "long"
                        },
                        "end_battery_level": {
                            "type": "float"
                        },
                        "end_lat": {
                            "type": "float"
                        },
                        "end_lng": {
                            "type": "float"
                        },
                        "end_odometer": {
                            "type": "float"
                        },
                        "end_position_id": {
                            "type": "float"
                        },
                        "end_time": {
                            "type": "date"
                        },
                        "end_time_date": {
                            "type": "date"
                        },
                        "end_time_epoch": {
                            "type": "long"
                        },
                        "end_time_time": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "engine_seconds": {
                            "type": "long"
                        },
                        "excessive_idle_seconds": {
                            "type": "long"
                        },
                        "excessive_over_speed_seconds": {
                            "type": "long"
                        },
                        "final_penalty": {
                            "type": "long"
                        },
                        "fuel_consumption": {
                            "type": "float"
                        },
                        "geo_in_count": {
                            "type": "long"
                        },
                        "geo_out_count": {
                            "type": "long"
                        },
                        "harsh_acceleration": {
                            "type": "long"
                        },
                        "harsh_acceleration_penalty": {
                            "type": "long"
                        },
                        "harsh_braking": {
                            "type": "long"
                        },
                        "harsh_braking_penalty": {
                            "type": "long"
                        },
                        "harsh_cornering": {
                            "type": "long"
                        },
                        "harsh_turn_penalty": {
                            "type": "long"
                        },
                        "id": {
                            "type": "long"
                        },
                        "idle_seconds": {
                            "type": "long"
                        },
                        "ign_off_count": {
                            "type": "long"
                        },
                        "ign_on_count": {
                            "type": "long"
                        },
                        "ignition_records": {
                            "type": "long"
                        },
                        "indexed_at": {
                            "type": "date"
                        },
                        "lat": {
                            "type": "float"
                        },
                        "lng": {
                            "type": "float"
                        },
                        "max_speed": {
                            "type": "float"
                        },
                        "max_speed_time": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "max_speed_time_date": {
                            "type": "date"
                        },
                        "max_speed_time_epoch": {
                            "type": "long"
                        },
                        "max_speed_time_time": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "more_events_penalty": {
                            "type": "long"
                        },
                        "motion_records": {
                            "type": "long"
                        },
                        "motion_seconds": {
                            "type": "long"
                        },
                        "night_driving": {
                            "type": "long"
                        },
                        "over_ignition": {
                            "type": "long"
                        },
                        "over_motion": {
                            "type": "long"
                        },
                        "over_speed": {
                            "type": "long"
                        },
                        "over_speed_penalty": {
                            "type": "long"
                        },
                        "over_speed_seconds": {
                            "type": "long"
                        },
                        "penalty_list": {
                            "properties": {
                                "count": {
                                    "type": "long"
                                },
                                "penalty": {
                                    "type": "long"
                                },
                                "type": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword",
                                            "ignore_above": 256
                                        }
                                    }
                                },
                                "weight": {
                                    "type": "long"
                                }
                            }
                        },
                        "penalty_per_km": {
                            "type": "float"
                        },
                        "position_id": {
                            "type": "long"
                        },
                        "server_id": {
                            "type": "long"
                        },
                        "start_battery": {
                            "type": "long"
                        },
                        "start_battery_level": {
                            "type": "float"
                        },
                        "start_lat": {
                            "type": "float"
                        },
                        "start_lng": {
                            "type": "float"
                        },
                        "start_odometer": {
                            "type": "float"
                        },
                        "start_position_id": {
                            "type": "float"
                        },
                        "start_time": {
                            "type": "date"
                        },
                        "start_time_date": {
                            "type": "date"
                        },
                        "start_time_epoch": {
                            "type": "long"
                        },
                        "start_time_time": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "stop_idle_date": {
                            "type": "date"
                        },
                        "stop_seconds": {
                            "type": "long"
                        },
                        "summary_date": {
                            "type": "date"
                        },
                        "timestamp": {
                            "type": "date"
                        },
                        "timestamp_date": {
                            "type": "date"
                        },
                        "timestamp_epoch": {
                            "type": "long"
                        },
                        "timestamp_time": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "trip_date": {
                            "type": "date"
                        },
                        "type": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "utilization": {
                            "type": "float"
                        }
                    }
                }
            },
            {
                "index": "stop_idle_reports",
                "mappings": {
                    "properties": {
                        "device_id": {
                            "type": "long"
                        },
                        "device_name": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "duration_seconds": {
                            "type": "long"
                        },
                        "end_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "engine_seconds": {
                            "type": "long"
                        },
                        "id": {
                            "type": "long"
                        },
                        "indexed_at": {
                            "type": "date"
                        },
                        "lat": {
                            "type": "float"
                        },
                        "lng": {
                            "type": "float"
                        },
                        "position_id": {
                            "type": "long"
                        },
                        "server_id": {
                            "type": "integer"
                        },
                        "start_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "stop_idle_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "timestamp": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                        },
                        "timestamp_column1": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "timestamp_column2": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "timestamp_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "timestamp_epoch": {
                            "type": "long"
                        },
                        "timestamp_time": {
                            "type": "keyword",
                            "ignore_above": 64
                        },
                        "type": {
                            "type": "keyword"
                        }
                    }
                }
            },
            {
                "index": "trip_reports",
                "mappings": {
                    "properties": {
                        "avg_speed": {
                            "type": "float"
                        },
                        "crash": {
                            "type": "integer"
                        },
                        "device_id": {
                            "type": "long"
                        },
                        "device_name": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "distance": {
                            "type": "float"
                        },
                        "driving_safety_score": {
                            "type": "float"
                        },
                        "driving_score": {
                            "type": "float"
                        },
                        "duration": {
                            "type": "long"
                        },
                        "duration_seconds": {
                            "type": "long"
                        },
                        "end_battery": {
                            "type": "integer"
                        },
                        "end_battery_level": {
                            "type": "float"
                        },
                        "end_lat": {
                            "type": "float"
                        },
                        "end_lng": {
                            "type": "float"
                        },
                        "end_odometer": {
                            "type": "double"
                        },
                        "end_position_id": {
                            "type": "long"
                        },
                        "end_soc": {
                            "type": "float"
                        },
                        "end_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "end_voltage": {
                            "type": "float"
                        },
                        "engine_seconds": {
                            "type": "long"
                        },
                        "excessive_idle_seconds": {
                            "type": "long"
                        },
                        "excessive_over_speed_seconds": {
                            "type": "long"
                        },
                        "final_penalty": {
                            "type": "float"
                        },
                        "harsh_acceleration": {
                            "type": "integer"
                        },
                        "harsh_acceleration_penalty": {
                            "type": "float"
                        },
                        "harsh_braking": {
                            "type": "integer"
                        },
                        "harsh_braking_penalty": {
                            "type": "float"
                        },
                        "harsh_cornering": {
                            "type": "integer"
                        },
                        "harsh_turn_penalty": {
                            "type": "float"
                        },
                        "id": {
                            "type": "long"
                        },
                        "idle_seconds": {
                            "type": "long"
                        },
                        "ignition_records": {
                            "type": "integer"
                        },
                        "indexed_at": {
                            "type": "date"
                        },
                        "max_speed": {
                            "type": "float"
                        },
                        "max_speed_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "more_events_penalty": {
                            "type": "float"
                        },
                        "motion_records": {
                            "type": "integer"
                        },
                        "motion_seconds": {
                            "type": "long"
                        },
                        "night_driving": {
                            "type": "integer"
                        },
                        "over_ignition": {
                            "type": "integer"
                        },
                        "over_motion": {
                            "type": "integer"
                        },
                        "over_speed": {
                            "type": "integer"
                        },
                        "over_speed_penalty": {
                            "type": "float"
                        },
                        "over_speed_seconds": {
                            "type": "long"
                        },
                        "penalty_list": {
                            "type": "nested",
                            "properties": {
                                "count": {
                                    "type": "integer"
                                },
                                "penalty": {
                                    "type": "float"
                                },
                                "type": {
                                    "type": "keyword"
                                },
                                "weight": {
                                    "type": "integer"
                                }
                            }
                        },
                        "penalty_per_km": {
                            "type": "float"
                        },
                        "power_difference": {
                            "type": "float"
                        },
                        "power_end": {
                            "type": "float"
                        },
                        "power_start": {
                            "type": "float"
                        },
                        "server_id": {
                            "type": "integer"
                        },
                        "start_battery": {
                            "type": "integer"
                        },
                        "start_battery_level": {
                            "type": "float"
                        },
                        "start_lat": {
                            "type": "float"
                        },
                        "start_lng": {
                            "type": "float"
                        },
                        "start_odometer": {
                            "type": "double"
                        },
                        "start_position_id": {
                            "type": "long"
                        },
                        "start_soc": {
                            "type": "float"
                        },
                        "start_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss.SSS Z||yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"
                        },
                        "start_voltage": {
                            "type": "float"
                        },
                        "timestamp": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                        },
                        "timestamp_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "timestamp_epoch": {
                            "type": "long"
                        },
                        "timestamp_time": {
                            "type": "keyword",
                            "ignore_above": 64
                        },
                        "trip_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "utilization": {
                            "type": "float"
                        }
                    }
                }
            },

        ],
        query_instructions=[
            "Always add relevant columns to the query based on the user's request and columns which enhances user experience, add columns which will improve summary and charts. ",
            "Do not fetch more than 100 rows unless the user explicitly requests more data",
            "IMPORTANT: Use the 'summary_reports' index as the DEFAULT index for all queries unless specifically directed otherwise. "
            "This index contains daily aggregated vehicle data and is appropriate for most queries including distance covered, speed metrics, and general vehicle performance. "
            "The summary_reports index MUST be used for any query about distance covered by vehicles, regardless of whether the query mentions 'summary' or not.",

            "Use the 'trip_reports' index ONLY when the user explicitly asks for individual trip details or when they specifically mention the word 'trip' or 'journey'. "
            "This index contains data about individual trips within a day.",

            "Use the 'stop_idle_reports' index ONLY when the user specifically asks about stopping or idling events. "
            "This index contains data about when vehicles stopped or idled."
        ],

        vector_db="bolt_support_doc",
        goal=(
            "Provide accurate and helpful responses to Bolt Delivery SaaS clients for both support and reporting-related queries. "
            "Use the vector database for support documentation, and leverage Elasticsearch schemas to generate meaningful summaries and charts for reporting questions."
        ),

        success_criteria=(
            "Deliver correct and context-aware answers to support and reporting queries by utilizing the 'bolt_support_doc' vector database "
            "and Elasticsearch index mappings. Ensure reporting responses include relevant data summaries and visualizations when appropriate."
        )
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
        vector_db="synco_support_doc",
        query_instructions=[],
        goal="Assist Synco Delivery SaaS clients with support and reporting questions, using the provided vector database and Elasticsearch schemas.",
        success_criteria=" Successfully answer support and reporting questions using the provided vector database and Elasticsearch schemas."
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
        vector_db="docling_documents",
        query_instructions=[],
        goal="Assist police departments with general support questions and provide information on various topics, using the provided vector database.",
        success_criteria=" Successfully answer general support questions using the provided vector database."
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
