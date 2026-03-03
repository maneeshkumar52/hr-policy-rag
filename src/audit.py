"""Cosmos DB audit logger for compliance."""
import structlog
from src.config import get_settings
from src.models import AuditRecord

logger = structlog.get_logger(__name__)


class AuditLogger:
    """Writes immutable audit records to Cosmos DB."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def log_query(self, record: AuditRecord) -> None:
        """
        Write an audit record to Cosmos DB.

        Args:
            record: Complete audit record including query, response, timing.
        """
        try:
            from azure.cosmos.aio import CosmosClient
            async with CosmosClient(url=self.settings.cosmos_endpoint, credential=self.settings.cosmos_key) as client:
                db = client.get_database_client(self.settings.cosmos_database)
                container = db.get_container_client(self.settings.cosmos_container)
                doc = record.model_dump()
                doc["timestamp"] = doc["timestamp"].isoformat()
                doc["_partitionKey"] = record.user_id
                # TTL: 7 years in seconds
                doc["ttl"] = 7 * 365 * 24 * 3600
                await container.create_item(body=doc)
                logger.info("audit_record_written", audit_id=record.id, user_id=record.user_id)
        except Exception as exc:
            logger.error("audit_write_failed", error=str(exc), audit_id=record.id)
