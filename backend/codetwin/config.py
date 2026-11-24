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
DEV_JWT_SECRET = "dev-only-change-me-dev-only-change-me"


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

    jwt_secret: str = DEV_JWT_SECRET
    jwt_minutes: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]

    # How many reverse proxies in front of the API append to X-Forwarded-For. 0 (local) uses the socket
    # address; 1 on App Service, whose front end appends the real client address as the last entry.
    # Entries further left are written by the client and never trusted.
    trusted_proxy_hops: int = 0

    # largest request body the API reads, for anything that is not a file upload
    max_json_bytes: int = 256 * 1024

    # a running run whose worker has not reported for this long is marked failed and can be retried
    run_heartbeat_seconds: int = 20
    run_stale_seconds: int = 300

    # upload limits
    max_archive_bytes: int = 20 * 1024 * 1024
    max_file_bytes: int = 512 * 1024
    max_archive_entries: int = 500
    max_evidence_bytes: int = 5 * 1024 * 1024

    # login throttling
    login_max_failures: int = 5
    login_lockout_seconds: int = 900

    # public endpoints (student sign-up, landing-page demo): attempts per client IP per window
    signup_max_per_hour: int = 5
    demo_max_per_minute: int = 20
    demo_max_chars: int = 20_000
    # public form submissions per client IP per hour; generous because a whole lab often shares one address
    form_max_per_hour: int = 120
    # wrong receipt codes per client IP per 15 minutes before the results page locks that address
    results_max_failures: int = 20

    # similarity
    embedder: str = "hashing"          # "hashing" (no download) or "unixcoder"
    model_path: Path | None = None     # defaults to the trained model for the chosen embedder

    @property
    def is_production(self) -> bool:
        return self.storage_backend == "azure" or self.database_url.startswith("mssql://")

    def check_secrets(self) -> None:
        """Refuse to start a production service with the development signing key."""
        if self.is_production and (self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32):
            raise RuntimeError("CODETWIN_JWT_SECRET must be set to a random value of at least 32 characters "
                               "(or stored in Key Vault) before running against Azure")


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
