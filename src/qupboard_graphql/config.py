"""
Application configuration loaded from environment variables.

Settings are read by Pydantic-Settings and fall back to sensible defaults
so that the service starts without any environment configuration.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings resolved from environment variables.

    Attributes:
        GRAPHQL_PATH: URL prefix at which the GraphQL endpoint is mounted.
        REST_PATH: URL prefix at which the REST API is mounted.
        DATABASE_URL: SQLAlchemy-compatible database connection URL.
    """

    GRAPHQL_PATH: str = "/graphql"
    REST_PATH: str = "/rest"
    DATABASE_URL: str = "sqlite+aiosqlite:///./qupboard.db"


settings = Settings()
