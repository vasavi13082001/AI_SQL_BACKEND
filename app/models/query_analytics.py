"""PostgreSQL models for query history and execution analytics."""

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QueryHistory(Base):
    """Stores NL query requests and lifecycle state."""

    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="received", index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    prompts: Mapped[list["UserPrompt"]] = relationship(
        "UserPrompt",
        back_populates="query_history",
        cascade="all, delete-orphan",
    )
    generated_sql_records: Mapped[list["GeneratedSQL"]] = relationship(
        "GeneratedSQL",
        back_populates="query_history",
        cascade="all, delete-orphan",
    )
    execution_analytics: Mapped["ExecutionAnalytics | None"] = relationship(
        "ExecutionAnalytics",
        back_populates="query_history",
        uselist=False,
        cascade="all, delete-orphan",
    )


class UserPrompt(Base):
    """Stores normalized prompt inputs used during SQL generation."""

    __tablename__ = "user_prompts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    query_history: Mapped["QueryHistory"] = relationship("QueryHistory", back_populates="prompts")


class GeneratedSQL(Base):
    """Stores SQL generated from prompts with validation metadata."""

    __tablename__ = "generated_sql"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    sql_dialect: Mapped[str] = mapped_column(String(30), nullable=False, default="snowflake")
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    query_history: Mapped["QueryHistory"] = relationship("QueryHistory", back_populates="generated_sql_records")
    execution_analytics: Mapped[list["ExecutionAnalytics"]] = relationship(
        "ExecutionAnalytics",
        back_populates="generated_sql",
    )


class ExecutionAnalytics(Base):
    """Stores execution-level analytics for generated SQL statements."""

    __tablename__ = "execution_analytics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_history.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    generated_sql_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_sql.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    warehouse_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    warehouse_query_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rows_returned: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bytes_scanned: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    credits_used: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    query_history: Mapped["QueryHistory"] = relationship("QueryHistory", back_populates="execution_analytics")
    generated_sql: Mapped["GeneratedSQL | None"] = relationship("GeneratedSQL", back_populates="execution_analytics")


class WarehousePerformanceMetric(Base):
    """Stores aggregated warehouse performance metrics per time window."""

    __tablename__ = "warehouse_performance_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    warehouse_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    metric_hour: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    total_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_execution_time_ms: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    p95_execution_time_ms: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    avg_queue_time_ms: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    avg_compilation_time_ms: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    avg_credits_per_query: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_bytes_scanned: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    metric_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
