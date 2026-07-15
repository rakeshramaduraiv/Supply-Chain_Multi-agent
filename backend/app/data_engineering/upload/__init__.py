"""
AMASCI Upload Service
======================
Handles CSV file upload, integrity hashing, versioning, and staging.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.enums import DatasetStatus, DatasetType
from app.exceptions import (
    EmptyDatasetException,
    FileTooLargeException,
    InvalidFileFormatException,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class UploadService:
    """Manages dataset upload lifecycle."""

    SUPPORTED_EXTENSIONS = {".csv"}
    SUPPORTED_ENCODINGS = ["utf-8", "latin-1", "iso-8859-1"]

    def __init__(self) -> None:
        self.upload_dir = settings.upload_path

    async def process_upload(
        self,
        file: UploadFile,
        dataset_type: DatasetType,
        description: str = "",
    ) -> dict:
        """
        Process an uploaded CSV file.

        Steps:
        1. Validate file format and size
        2. Compute SHA-256 hash for deduplication
        3. Save to staging directory
        4. Parse CSV into DataFrame
        5. Generate upload metadata
        """
        self._validate_file_format(file.filename or "")
        content = await file.read()
        self._validate_file_size(content)

        file_hash = self._compute_hash(content)
        dataset_id = str(uuid.uuid4())
        version = 1

        file_path = self._save_file(content, dataset_id)
        df = self._parse_csv(content)

        if df.empty:
            raise EmptyDatasetException()

        metadata = {
            "dataset_id": dataset_id,
            "version": version,
            "filename": file.filename,
            "dataset_type": dataset_type.value,
            "description": description,
            "file_hash": file_hash,
            "file_path": str(file_path),
            "file_size_bytes": len(content),
            "file_size_mb": round(len(content) / (1024 * 1024), 2),
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "status": DatasetStatus.UPLOADED.value,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Dataset uploaded: {file.filename}",
            extra={
                "dataset_id": dataset_id,
                "rows": len(df),
                "columns": len(df.columns),
                "size_mb": metadata["file_size_mb"],
            },
        )

        return metadata

    def _validate_file_format(self, filename: str) -> None:
        """Ensure file has a supported extension."""
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise InvalidFileFormatException(filename)

    def _validate_file_size(self, content: bytes) -> None:
        """Ensure file does not exceed maximum size."""
        size_mb = len(content) / (1024 * 1024)
        if size_mb > settings.max_upload_size_mb:
            raise FileTooLargeException(size_mb, settings.max_upload_size_mb)

    def _compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash for file integrity and deduplication."""
        return hashlib.sha256(content).hexdigest()

    def _save_file(self, content: bytes, dataset_id: str) -> Path:
        """Save raw file to staging directory."""
        file_path = self.upload_dir / f"{dataset_id}.csv"
        file_path.write_bytes(content)
        return file_path

    def _parse_csv(self, content: bytes) -> pd.DataFrame:
        """Parse CSV content into DataFrame with encoding detection."""
        import io

        for encoding in self.SUPPORTED_ENCODINGS:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                return df
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue

        raise InvalidFileFormatException("Unable to parse CSV with supported encodings")

    def load_dataset(self, dataset_id: str) -> pd.DataFrame:
        """Load a previously uploaded dataset from disk."""
        file_path = self.upload_dir / f"{dataset_id}.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {dataset_id}")

        for encoding in self.SUPPORTED_ENCODINGS:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                continue

        raise InvalidFileFormatException(f"Cannot read dataset {dataset_id}")
