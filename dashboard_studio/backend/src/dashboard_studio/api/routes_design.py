from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dashboard_studio.api.deps import get_anthropic_client, get_db_session, get_upload_store
from dashboard_studio.db.models import TokenPreset
from dashboard_studio.design.anthropic_client import (
    AnthropicDesignClient,
    DesignAnalysisAuthError,
    DesignAnalysisNotConfiguredError,
    DesignAnalysisRateLimitError,
    DesignAnalysisUpstreamError,
)
from dashboard_studio.design.theme_export import ThemeNameError, render_theme_yaml
from dashboard_studio.design.tokens import DesignTokenSet
from dashboard_studio.design.uploads import DesignUploadStore, UploadValidationError

router = APIRouter(prefix="/api/design", tags=["design"])


class UploadResponse(BaseModel):
    upload_id: str
    media_type: str
    size_bytes: int


class UsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model: str


class AnalyzeRequest(BaseModel):
    upload_id: str


class AnalyzeResponse(BaseModel):
    tokens: DesignTokenSet
    usage: UsageInfo


class TokenPresetSummary(BaseModel):
    id: str
    name: str
    created_at: datetime


class TokenPresetDetail(BaseModel):
    id: str
    name: str
    created_at: datetime
    tokens: DesignTokenSet


class TokenPresetCreate(BaseModel):
    name: str
    tokens: DesignTokenSet


class ThemeExportRequest(BaseModel):
    theme_name: str
    tokens: DesignTokenSet


class ThemeExportResponse(BaseModel):
    filename: str
    yaml: str


@router.post("/upload", response_model=UploadResponse)
async def upload_design_image(
    store: Annotated[DesignUploadStore, Depends(get_upload_store)],
    file: UploadFile,
) -> UploadResponse:
    content = await file.read()
    media_type = file.content_type or ""
    try:
        upload_id, _path = store.save(content, media_type)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(upload_id=upload_id, media_type=media_type, size_bytes=len(content))


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_design(
    body: AnalyzeRequest,
    store: Annotated[DesignUploadStore, Depends(get_upload_store)],
    client: Annotated[AnthropicDesignClient, Depends(get_anthropic_client)],
) -> AnalyzeResponse:
    path = store.resolve(body.upload_id)
    media_type = DesignUploadStore.media_type_for(path) if path is not None else None
    if path is None or media_type is None:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden.")

    image_bytes = path.read_bytes()

    try:
        result = await client.analyze_design(image_bytes, media_type)
    except DesignAnalysisNotConfiguredError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except DesignAnalysisAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DesignAnalysisRateLimitError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except DesignAnalysisUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AnalyzeResponse(
        tokens=result.tokens,
        usage=UsageInfo(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            model=result.model,
        ),
    )


@router.get("/presets", response_model=list[TokenPresetSummary])
async def list_token_presets(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[TokenPresetSummary]:
    result = await session.execute(select(TokenPreset).order_by(TokenPreset.created_at.desc()))
    return [
        TokenPresetSummary(id=preset.id, name=preset.name, created_at=preset.created_at)
        for preset in result.scalars()
    ]


@router.get("/presets/{preset_id}", response_model=TokenPresetDetail)
async def get_token_preset(
    preset_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPresetDetail:
    preset = await session.get(TokenPreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset nicht gefunden.")
    return TokenPresetDetail(
        id=preset.id,
        name=preset.name,
        created_at=preset.created_at,
        tokens=DesignTokenSet.model_validate_json(preset.token_json),
    )


@router.post("/presets", response_model=TokenPresetDetail)
async def create_token_preset(
    body: TokenPresetCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPresetDetail:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset-Name darf nicht leer sein.")

    preset = TokenPreset(
        name=name,
        token_json=body.tokens.model_dump_json(),
        token_schema_version=body.tokens.schema_version,
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)

    return TokenPresetDetail(
        id=preset.id, name=preset.name, created_at=preset.created_at, tokens=body.tokens
    )


@router.delete("/presets/{preset_id}")
async def delete_token_preset(
    preset_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, bool]:
    preset = await session.get(TokenPreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset nicht gefunden.")
    await session.delete(preset)
    await session.commit()
    return {"deleted": True}


@router.post("/theme-export", response_model=ThemeExportResponse)
async def export_theme(body: ThemeExportRequest) -> ThemeExportResponse:
    try:
        yaml_text = render_theme_yaml(body.theme_name, body.tokens)
    except ThemeNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_name = body.theme_name.strip().lower().replace(" ", "_")
    return ThemeExportResponse(filename=f"{safe_name}.yaml", yaml=yaml_text)
