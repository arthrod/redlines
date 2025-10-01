from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ChangeType = Literal["equal", "insert", "delete", "replace"]


class DiffSegment(BaseModel):
    """Represents a portion of the compared documents."""

    model_config = ConfigDict(extra="forbid")

    start: Optional[int] = Field(default=None, ge=0, description="Start index of the segment in token sequence")
    end: Optional[int] = Field(default=None, ge=0, description="End index of the segment in token sequence")
    text: Optional[str] = Field(default=None, description="Raw text content of the segment")
    xpath: Optional[str] = Field(default=None, description="XPath location for structured formats like HTML/XML")


class DiffChange(BaseModel):
    """Represents a single change entry in the structured diff output."""

    model_config = ConfigDict(extra="forbid")

    type: ChangeType = Field(description="Type of change detected between source and test documents")
    source: DiffSegment = Field(description="Source-side segment information")
    test: DiffSegment = Field(description="Test-side segment information")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Processor-specific metadata for the change")


class DiffSummary(BaseModel):
    """Aggregated summary data for a diff run."""

    model_config = ConfigDict(extra="forbid")

    total_changes: int = Field(ge=0, description="Total number of change entries returned")
    insertions: int = Field(ge=0, description="Number of insertion operations")
    deletions: int = Field(ge=0, description="Number of deletion operations")
    replacements: int = Field(ge=0, description="Number of replacement operations")
    equals: int = Field(ge=0, description="Number of equal segments without changes")


class DiffMetadata(BaseModel):
    """Metadata describing the diff execution context."""

    model_config = ConfigDict(extra="allow")

    generated_at: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp when the diff was generated")
    library_version: str = Field(description="Version of the redlines library that produced the diff")
    style: Optional[str] = Field(default=None, description="Active markdown style applied during diff rendering")
    processor: str = Field(description="Processor implementation that produced the diff output")


class DiffResult(BaseModel):
    """Structured representation of a diff suitable for JSON serialization."""

    model_config = ConfigDict(extra="forbid")

    metadata: DiffMetadata
    summary: DiffSummary
    changes: list[DiffChange]


class DiffResponse(DiffResult):
    """Response payload for API diff endpoints."""

    model_config = ConfigDict(extra="forbid")


class DiffRequest(BaseModel):
    """Request payload for performing a diff operation via the API."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="Original/source document content to compare")
    test: str = Field(description="Changed/test document content to compare")
    source_format: Optional[str] = Field(default=None, description="Optional hint describing the format of the source content")
    test_format: Optional[str] = Field(default=None, description="Optional hint describing the format of the test content")
    markdown_style: Optional[str] = Field(default=None, description="Markdown style identifier to use while rendering outputs")
    options: dict[str, Any] = Field(default_factory=dict, description="Additional keyword arguments passed to Redlines constructor")


class ConvertRequest(BaseModel):
    """Request payload for invoking ConversionManager helpers via the API."""

    model_config = ConfigDict(extra="forbid")

    data: Any = Field(description="Payload to be converted or extracted")
    source_format: str = Field(description="Input format identifier for the payload")
    target_format: Optional[str] = Field(default=None, description="Target format identifier when performing a conversion")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata forwarded to the conversion manager")


class ConvertResponse(BaseModel):
    """Response payload for conversion operations."""

    model_config = ConfigDict(extra="forbid")

    result: Any = Field(description="Converted payload or extracted text")
    source_format: str = Field(description="Original format of the processed payload")
    target_format: Optional[str] = Field(default=None, description="Target format that produced the result")


class HealthResponse(BaseModel):
    """Health check response model."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = Field(default="ok", description="Overall system status indicator")
    version: str = Field(description="Version of the redlines library handling requests")
