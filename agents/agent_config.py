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
                        "driver_name": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "driving_safety_score": {
                            "type": "integer"
                        },
                        "driving_score": {
                            "type": "long"
                        },
                        "duration": {
                            "type": "long"
                        },
                        "end_lat": {
                            "type": "float"
                        },
                        "end_lng": {
                            "type": "float"
                        },
                        "end_position_id": {
                            "type": "long"
                        },
                        "end_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
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
                        "engine_2_seconds": {
                            "type": "long"
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
                        "first_ignition_on": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                        },
                        "first_position_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                        },
                        "fuel_consumption": {
                            "type": "float"
                        },
                        "geo_in_count": {
                            "type": "integer"
                        },
                        "geo_in_distance": {
                            "type": "float"
                        },
                        "geo_in_end": {
                            "type": "integer"
                        },
                        "geo_in_seconds": {
                            "type": "long"
                        },
                        "geo_out_count": {
                            "type": "integer"
                        },
                        "geo_out_distance": {
                            "type": "float"
                        },
                        "geo_out_seconds": {
                            "type": "long"
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
                        "ign_off_count": {
                            "type": "integer"
                        },
                        "ign_on_count": {
                            "type": "integer"
                        },
                        "ignition_records": {
                            "type": "long"
                        },
                        "indexed_at": {
                            "type": "date"
                        },
                        "last_battery": {
                            "type": "float"
                        },
                        "last_battery_level": {
                            "type": "float"
                        },
                        "last_ignition_on": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                        },
                        "last_position_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
                        },
                        "max_speed": {
                            "type": "float"
                        },
                        "max_speed_time": {
                            "type": "date"
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
                        "penalty_per_km": {
                            "type": "float"
                        },
                        "power_cut_counts": {
                            "type": "integer"
                        },
                        "raw_positions_count": {
                            "type": "long"
                        },
                        "region": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "server_id": {
                            "type": "long"
                        },
                        "start_battery": {
                            "type": "float"
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
                        "start_position_id": {
                            "type": "long"
                        },
                        "start_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd HH:mm:ss||epoch_millis"
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
                        "stop_report_count": {
                            "type": "integer"
                        },
                        "stop_seconds": {
                            "type": "long"
                        },
                        "summary_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
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
                        "utilization": {
                            "type": "float"
                        },
                        "vehicle_type": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
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
            # General rules
            "All queries must use valid Elasticsearch DSL.",
            "Use the index `summary_reports` unless specified otherwise.",
            "Each query should be self-contained and syntactically correct.",
            "Avoid referencing parent or sibling aggregations using relative paths like '../some_agg'. This is not supported in Elasticsearch.",

            # Field usage guidance
            "Use the following standard field mappings for metrics:",
            "- `distance` for distance in kilometers.",
            "- `avg_speed` for average speed in km/h.",
            "- `utilization` for usage percentage.",
            "- `summary_date` or `timestamp_date` for date-based filters or histograms.",
            "- `device_id`, `device_name` for device-level grouping.",
            "- `driving_score` and `driving_safety_score` for performance analysis.",

            # Date and time handling
            "Always filter by a date range using `summary_date` or `timestamp_date`.",
            "Use `date_histogram` instead of `terms` on `date` fields. Set `calendar_interval` to `day`, `week`, or `month` as needed.",
            "For recent data, use: `gte: now/M`, `lte: now` (for current month).",

            # Aggregations and metrics
            "To calculate trends over time, use `date_histogram` + metric aggregation (e.g., `avg` on `distance`).",
            "To compare days with a monthly average, run two separate queries: first compute monthly average, then filter daily values using a fixed threshold.",
            "Avoid using `bucket_selector` with cross-level references. Instead, use inline `script` comparisons to constants.",

            # Response formatting
            "Include `_source` fields explicitly if returning documents.",
            "Sort results by `summary_date` or `timestamp_date` descending when showing recent trends.",

            # Example patterns
            "Example: Daily trend of distance in current month:",
            "- Use `date_histogram` on `summary_date` with `calendar_interval: day`.",
            "- Use `avg` aggregation on `distance` within each bucket.",

            "Example: Filter devices with avg speed > 60 in current month:",
            "- Use `range` filter on `summary_date`.",
            "- Use `terms` aggregation on `device_id` or `device_name.keyword`.",
            "- Use `avg` on `avg_speed` and a `bucket_selector` with threshold script.",

            # Index-specific guidance
            "Use `summary_reports` for overall daily metrics per device.",
            "Use `trip_reports` for trip-level analysis (more granular).",
            "Use `stop_idle_reports` for idle or stop durations on a given day.",

            # Filters and constraints
            "Do not perform joins between indices. Elasticsearch does not support multi-index joins.",
            "Use filters inside the `query.bool.filter` array only.",

            # Visualizations
            "If asked to generate visual summaries or chart-friendly data, use aggregations over time (like `date_histogram`) and ensure bucket keys are sorted in descending order."
        ],
        dsl_rules=[
            {
                "invalid": "buckets_path: ../avg_monthly_distance",
                "reason": "Elasticsearch does not support referencing sibling/parent aggregations from within nested aggregations.",
                "fix": "Run the monthly average calculation as a separate query and inject the value as a constant."
            },
            {
                "field": "summary_date",
                "preferred_agg": "date_histogram",
                "reason": "`summary_date` is a `date` field and should be aggregated using a date histogram, not a terms aggregation."
            },
            {
                "aggregation": "bucket_selector",
                "allowed_context": "within same aggregation level only",
                "reason": "`bucket_selector` must only reference sibling aggregations within the same bucket."
            },
            {
                "fields": ["timestamp_date", "summary_date"],
                "filter_format": "range",
                "example": {
                    "range": {
                        "summary_date": {
                            "gte": "now/M",
                            "lte": "now"
                        }
                    }
                },
                "reason": "Always filter date fields using a `range` clause."
            },
            {
                "index": "summary_reports",
                "allowed_fields": [
                    "distance", "avg_speed", "utilization",
                    "summary_date", "device_id", "device_name", "driving_score"
                ],
                "reason": "Restrict aggregations and filters to relevant fields only to ensure semantic accuracy."
            }
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
        success_criteria=" Successfully answer support and reporting questions using the provided vector database and Elasticsearch schemas.",
        dsl_rules=[],
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
        success_criteria=" Successfully answer general support questions using the provided vector database.",
        dsl_rules=[],
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
