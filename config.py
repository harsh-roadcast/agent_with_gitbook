"""Legacy configuration file - now uses the new modular configuration system."""
from core.config import config_manager

# Export the new configuration for backward compatibility
settings = config_manager.config

# Legacy class for backward compatibility
class Settings:
    """Legacy Settings class that delegates to the new configuration system."""

    @property
    def OPENAI_API_KEY(self):
        return settings.models.openai_api_key

# Create instance for backward compatibility
settings_legacy = Settings()
