"""Configuration management for PilotLog."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    db_path: Path = Path.home() / ".pilotlog" / "logbook.db"

    # Server
    host: str = "127.0.0.1"
    port: int = 8090

    # Logging
    log_level: str = "INFO"
    log_path: Path = Path.home() / ".pilotlog" / "logs"

    # Import settings
    backup_before_import: bool = True

    model_config = {
        "env_prefix": "PILOTLOG_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
