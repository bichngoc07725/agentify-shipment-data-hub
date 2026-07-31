from typing import Any, final

from pydantic import BaseModel


class Metadata(BaseModel):
    name: str
    description: str


@final
class TagsMetadata:
    HEALTH: Metadata = Metadata(
        name="health", description="Service and database health."
    )
    AUTH: Metadata = Metadata(
        name="auth", description="User login and JWT issuance."
    )
    GMAIL_CONNECTIONS: Metadata = Metadata(
        name="gmail-connections", description="Connected Gmail mailboxes."
    )
    SYNC_JOBS: Metadata = Metadata(
        name="sync-jobs", description="Email sync tracking jobs."
    )
    INTERNAL_INGESTION: Metadata = Metadata(
        name="internal-ingestion",
        description="Internal ingestion APIs for task 1-2 services.",
    )
    CONTAINERS: Metadata = Metadata(
        name="containers",
        description="Container-centric search and detail APIs.",
    )
    EMAILS: Metadata = Metadata(
        name="emails", description="Stored source email detail APIs."
    )


class Configs:
    @staticmethod
    def get_tags_metadata() -> list[dict[str, Any]]:
        return [
            TagsMetadata.HEALTH.model_dump(),
            TagsMetadata.AUTH.model_dump(),
            TagsMetadata.GMAIL_CONNECTIONS.model_dump(),
            TagsMetadata.SYNC_JOBS.model_dump(),
            TagsMetadata.INTERNAL_INGESTION.model_dump(),
            TagsMetadata.CONTAINERS.model_dump(),
            TagsMetadata.EMAILS.model_dump(),
        ]
