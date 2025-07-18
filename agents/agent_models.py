"""Pydantic models for agent configuration."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    name: str = Field(..., description="Unique name identifier for the agent")
    system_prompt: str = Field(..., description="System prompt that defines the agent's role and behavior")
    es_schemas: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of Elasticsearch schemas the agent can use. Each schema is a dictionary containing schema definition"
    )
    vector_db: Optional[str] = Field(
        default=None,
        description="Vector database index name the agent can use for vector searches"
    )
    query_instructions: List[str] = Field(..., description="List of instructions for the agent to follow when processing queries")
    success_criteria: Optional[str] = Field(..., description="Criteria for determining if the agent's response is successful")
    goal: Optional[str] = Field(
        default=None,
        description="High-level goal or objective of the agent"
    )


    class Config:
        """Pydantic configuration."""
        json_encoders = {
            # Add any custom encoders if needed
        }
        validate_assignment = True


class AgentList(BaseModel):
    """Container for managing multiple agents."""

    agents: List[AgentConfig] = Field(
        default_factory=list,
        description="List of configured agents"
    )

    def add_agent(self, agent: AgentConfig) -> None:
        """Add an agent to the list."""
        # Check for duplicate names
        existing_names = [a.name for a in self.agents]
        if agent.name in existing_names:
            raise ValueError(f"Agent with name '{agent.name}' already exists")

        self.agents.append(agent)

    def get_agent_by_name(self, name: str) -> Optional[AgentConfig]:
        """Get an agent by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def remove_agent(self, name: str) -> bool:
        """Remove an agent by name. Returns True if removed, False if not found."""
        for i, agent in enumerate(self.agents):
            if agent.name == name:
                del self.agents[i]
                return True
        return False

    def list_agent_names(self) -> List[str]:
        """Get list of all agent names."""
        return [agent.name for agent in self.agents]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentList':
        """Create AgentList from dictionary."""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert AgentList to dictionary."""
        return self.dict()

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            # Add any custom encoders if needed
        }
        validate_assignment = True
