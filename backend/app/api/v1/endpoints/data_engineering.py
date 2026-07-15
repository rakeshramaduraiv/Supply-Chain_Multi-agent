"""
AMASCI Data Engineering API Endpoints
========================================
Upload, validate, clean, transform, and profile datasets.
"""

import logging
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.enums import DatasetType
from app.data_engineering.pipeline import DataEngineeringPipeline, PipelineResult
from app.data_engineering.profiling import ProfilingService
from app.data_engineering.upload import UploadService
from app.api.v1.endpoints.ws import broadcast_event
from app.schemas import BaseResponse
from app.schemas.data_engineering import (
    DatasetHistoryResponse,
    PipelineResultSchema,
    ProfileResponseSchema,
    UploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Data Engineering"])

# In-memory store for demo (replace with DB repository in production)
_dataset_store: dict[str, dict[str, Any]] = {}
_processed_store: dict[str, Any] = {}


@router.post(
    "/upload/train",
    response_model=BaseResponse[UploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Training Dataset",
    description="Upload a historical CSV dataset for model training.",
)
async def upload_training_dataset(
    file: UploadFile = File(..., description="CSV file to upload"),
    description: str = Form(default="", description="Dataset description"),
) -> BaseResponse[UploadResponse]:
    """Upload and register a historical training dataset."""
    upload_service = UploadService()
    metadata = await upload_service.process_upload(
        file=file,
        dataset_type=DatasetType.HISTORICAL,
        description=description,
    )

    # Store metadata
    _dataset_store[metadata["dataset_id"]] = metadata

    response_data = UploadResponse(**metadata)

    return BaseResponse(
        success=True,
        message=f"Training dataset uploaded successfully: {metadata['row_count']} rows",
        data=response_data,
    )


@router.post(
    "/upload/forecast",
    response_model=BaseResponse[UploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Forecast Dataset",
    description="Upload a dataset for generating forecasts.",
)
async def upload_forecast_dataset(
    file: UploadFile = File(..., description="CSV file to upload"),
    description: str = Form(default="", description="Dataset description"),
) -> BaseResponse[UploadResponse]:
    """Upload dataset for forecast generation."""
    upload_service = UploadService()
    metadata = await upload_service.process_upload(
        file=file,
        dataset_type=DatasetType.HISTORICAL,
        description=description,
    )

    _dataset_store[metadata["dataset_id"]] = metadata

    return BaseResponse(
        success=True,
        message=f"Forecast dataset uploaded: {metadata['row_count']} rows",
        data=UploadResponse(**metadata),
    )


@router.post(
    "/upload/actual",
    response_model=BaseResponse[UploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Actual Data",
    description="Upload actual next-month data for prediction comparison.",
)
async def upload_actual_dataset(
    file: UploadFile = File(..., description="CSV file to upload"),
    description: str = Form(default="", description="Dataset description"),
) -> BaseResponse[UploadResponse]:
    """Upload actual operational data for comparison with forecasts."""
    upload_service = UploadService()
    metadata = await upload_service.process_upload(
        file=file,
        dataset_type=DatasetType.ACTUALS,
        description=description,
    )

    _dataset_store[metadata["dataset_id"]] = metadata

    await broadcast_event("Actual Uploaded", {"dataset_id": metadata["dataset_id"]})
    await broadcast_event("Forecast Validated", {"dataset_id": metadata["dataset_id"]})

    return BaseResponse(
        success=True,
        message=f"Actual dataset uploaded: {metadata['row_count']} rows",
        data=UploadResponse(**metadata),
    )


@router.post(
    "/process/{dataset_id}",
    response_model=BaseResponse[PipelineResultSchema],
    status_code=status.HTTP_200_OK,
    summary="Process Dataset",
    description="Run the complete data engineering pipeline on an uploaded dataset.",
)
async def process_dataset(dataset_id: str) -> BaseResponse[PipelineResultSchema]:
    """Execute validation → cleaning → transformation → profiling pipeline."""
    if dataset_id not in _dataset_store:
        from app.exceptions import RecordNotFoundException
        raise RecordNotFoundException("Dataset", dataset_id)

    upload_service = UploadService()
    df = upload_service.load_dataset(dataset_id)

    pipeline = DataEngineeringPipeline()
    df_processed, result = pipeline.execute(df, dataset_id)

    # Store processed result
    _processed_store[dataset_id] = {
        "dataframe": df_processed,
        "result": result,
    }

    # Update dataset status
    _dataset_store[dataset_id]["status"] = result.status
    if result.validation_report:
        _dataset_store[dataset_id]["quality_score"] = result.validation_report.get("quality_score")

    await broadcast_event("Knowledge Graph Updated", {"dataset_id": dataset_id})

    return BaseResponse(
        success=result.status == "completed",
        message=f"Pipeline {result.status}: {result.row_count_raw}→{result.row_count_final} rows in {result.total_duration_ms:.0f}ms",
        data=PipelineResultSchema(**result.to_dict()),
    )


@router.get(
    "/dataset/{dataset_id}/profile",
    response_model=BaseResponse[ProfileResponseSchema],
    status_code=status.HTTP_200_OK,
    summary="Get Dataset Profile",
    description="Retrieve the data profile for a processed dataset.",
)
async def get_dataset_profile(dataset_id: str) -> BaseResponse[ProfileResponseSchema]:
    """Get comprehensive data profile for a processed dataset."""
    if dataset_id not in _processed_store:
        from app.exceptions import RecordNotFoundException
        raise RecordNotFoundException("Processed Dataset", dataset_id)

    stored = _processed_store[dataset_id]
    profile = stored["result"].profile

    return BaseResponse(
        success=True,
        message="Dataset profile retrieved",
        data=ProfileResponseSchema(**profile),
    )


@router.get(
    "/dataset/history",
    response_model=BaseResponse[DatasetHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Dataset History",
    description="List all uploaded datasets with metadata.",
)
async def get_dataset_history() -> BaseResponse[DatasetHistoryResponse]:
    """Retrieve upload history for all datasets."""
    datasets = []
    for ds_id, meta in _dataset_store.items():
        datasets.append({
            "dataset_id": ds_id,
            "version": meta.get("version", 1),
            "filename": meta.get("filename", ""),
            "dataset_type": meta.get("dataset_type", ""),
            "status": meta.get("status", "uploaded"),
            "row_count": meta.get("row_count", 0),
            "quality_score": meta.get("quality_score"),
            "uploaded_at": meta.get("uploaded_at", ""),
        })

    return BaseResponse(
        success=True,
        message=f"Found {len(datasets)} datasets",
        data=DatasetHistoryResponse(total=len(datasets), datasets=datasets),
    )


@router.get(
    "/dataset/{dataset_id}",
    response_model=BaseResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Get Dataset Info",
    description="Get metadata for a specific dataset.",
)
async def get_dataset_info(dataset_id: str) -> BaseResponse[dict]:
    """Get metadata for a specific uploaded dataset."""
    if dataset_id not in _dataset_store:
        from app.exceptions import RecordNotFoundException
        raise RecordNotFoundException("Dataset", dataset_id)

    return BaseResponse(
        success=True,
        message="Dataset info retrieved",
        data=_dataset_store[dataset_id],
    )
