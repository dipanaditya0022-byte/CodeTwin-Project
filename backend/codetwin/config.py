"""Settings for the API and the worker.

Locally everything comes from environment variables (or a .env file).
In Azure, set KEY_VAULT_URL and the app reads the database connection
string, the token signing key and the storage connection strings from
Key Vault through its managed identity.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODETWIN_", env_file=".env", extra="ignore")

    # "sqlite:///path/to/file.db" for local work, or "mssql://<ODBC connection string>" for Azure SQL
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'codetwin.db'}"

    # storage backends: "local" (folders under data_dir) or "azure"
    storage_backend: str = "local"
    data_dir: Path = REPO_ROOT / "data"
    azure_storage_connection_string: str | None = None
    blob_container: str = "codetwin"
    queue_name: str = "similarity-runs"
    cosmos_url: str | None = None
    cosmos_key: str | None = None
    cosmos_database: str = "codetwin"
    cosmos_container: str = "match_reports"

    key_vault_url: str | None = None

    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    jwt_minutes: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]

    # upload limits
    max_archive_bytes: int = 20 * 1024 * 1024
    max_file_bytes: int = 512 * 1024
    max_archive_entries: int = 500
    max_evidence_bytes: int = 5 * 1024 * 1024

    # login throttling
    login_max_failures: int = 5
    login_lockout_seconds: int = 900

    # similarity
    embedder: str = "hashing"          # "hashing" (no download) or "unixcoder"
    model_path: Path | None = None     # defaults to the trained model for the chosen embedder


def _load_from_key_vault(settings: Settings) -> Settings:
    """Override secrets with Key Vault values. Only used when KEY_VAULT_URL is set."""
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    client = SecretClient(vault_url=settings.key_vault_url, credential=DefaultAzureCredential())
    mapping = {
        "database_url": "codetwin-database-url",
        "jwt_secret": "codetwin-jwt-secret",
        "azure_storage_connection_string": "codetwin-storage-connection",
        "cosmos_key": "codetwin-cosmos-key",
    }
    updates = {field: client.get_secret(name).value for field, name in mapping.items()}
    return settings.model_copy(update=updates)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.key_vault_url:
        settings = _load_from_key_vault(settings)
    return settings
