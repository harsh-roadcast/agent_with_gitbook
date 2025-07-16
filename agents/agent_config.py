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
            {"schema": "vehicle_trip_summary", "columns": [
                "avg_speed", "center", "crash", "device_id", "device_name", "distance",
                "driving_safety_score", "driving_score", "end_lat", "end_lng", "end_odometer",
                "end_position_id", "end_time", "end_time_date", "end_time_time", "engine_2_seconds",
                "engine_seconds", "excessive_idle_seconds", "excessive_over_speed_seconds",
                "excessive_stop_seconds", "filter_positions_count", "final_penalty",
                "first_ignition_on", "first_position_time", "front", "frontLeft", "frontRight",
                "front_right_motor_time", "fuel_consumption", "geo_in_count", "geo_in_distance",
                "geo_in_end", "geo_in_seconds", "geo_out_count", "geo_out_distance", "geo_out_seconds",
                "harsh_acceleration", "harsh_acceleration_penalty", "harsh_braking",
                "harsh_braking_penalty", "harsh_cornering", "harsh_turn_penalty", "id", "idle_seconds",
                "ign_off_count", "ign_on_count", "ignition_records", "inside_geofence_ids",
                "last_battery", "last_battery_level", "last_ignition_on", "last_position_time",
                "low_batt_counts", "low_fuel_counts", "max_speed", "max_speed_time",
                "more_events_penalty", "motion_records", "motion_seconds", "night_driving",
                "over_ignition", "over_motion", "over_speed", "over_speed_penalty",
                "over_speed_seconds", "penalty_list", "penalty_list.count", "penalty_list.penalty",
                "penalty_list.type", "penalty_list.weight", "penalty_per_km", "power_cut_counts",
                "raw_positions_count", "server_id", "start_battery", "start_battery_level",
                "start_lat", "start_lng", "start_odometer", "start_position_id", "start_time",
                "start_time_date", "start_time_time", "steps", "stop_seconds", "summary_date",
                "utilization"
            ]},
            {"schema": "summary_reports", "columns": [
                "avg_speed", "crash", "device_id", "device_name", "distance", "driving_safety_score",
                "driving_score", "duration", "end_battery", "end_battery_level", "end_lat",
                "end_lng", "end_odometer", "end_position_id", "end_soc", "end_time", "end_time_date",
                "end_time_epoch", "end_time_time", "end_voltage", "excessive_idle_seconds",
                "excessive_over_speed_seconds", "final_penalty", "harsh_acceleration",
                "harsh_acceleration_penalty", "harsh_braking", "harsh_braking_penalty",
                "harsh_cornering", "harsh_turn_penalty", "id", "idle_seconds", "ignition_records",
                "max_speed", "max_speed_time", "max_speed_time_date", "max_speed_time_epoch",
                "max_speed_time_time", "more_events_penalty", "motion_records", "motion_seconds",
                "night_driving", "over_ignition", "over_motion", "over_speed", "over_speed_penalty",
                "over_speed_seconds", "penalty_list", "penalty_list.count", "penalty_list.penalty",
                "penalty_list.type", "penalty_list.weight", "penalty_per_km", "power_difference",
                "server_id", "start_battery", "start_battery_level", "start_lat", "start_lng",
                "start_odometer", "start_position_id", "start_soc", "start_time", "start_time_date",
                "start_time_epoch", "start_time_time", "start_voltage", "trip_date", "utilization"
            ]},
            {"schema": "vehicle_alarm_events", "columns": [
                "alarm", "deviceid", "driver_id", "fixtime", "fixtime_date", "fixtime_epoch",
                "fixtime_time", "geofenceid", "geofencename", "id", "latitude", "longitude",
                "positionid", "servertime", "servertime_date", "servertime_epoch", "servertime_time",
                "status", "tag_id", "type"
            ]},
            {"schema": "vehicle_stop_idle_reports", "columns": [
                "device_id", "device_name", "duration_seconds", "end_time", "end_time_date",
                "end_time_epoch", "end_time_time", "engine_seconds", "id", "lat", "lng",
                "position_id", "server_id", "start_time", "start_time_date", "start_time_epoch",
                "start_time_time", "stop_idle_date", "timestamp_column1", "timestamp_column2", "type"
            ]}
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
