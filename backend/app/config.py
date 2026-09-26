from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "anthropic/claude-sonnet-4.5"
    QDRANT_URL: str = "http://qdrant:6333"
    EMBEDDINGS_URL: str = "http://embeddings:80"
    RERANKER_URL: str = "http://reranker:80"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"
    # Below this top reranked score, /query abstains rather than asking the
    # LLM to answer from weak evidence.
    RERANK_ABSTAIN_THRESHOLD: float = 0.3
    # Comma-separated list of origins allowed to call this API from a browser
    # (CORS). Defaults cover the frontend's docker-compose port (3001) and
    # the default `next dev` port (3000) for running the frontend outside compose.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


settings = Settings()
