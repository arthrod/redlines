from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from importlib.metadata import PackageNotFoundError, version

from .models import ConvertRequest, ConvertResponse, DiffRequest, DiffResponse, HealthResponse
from .redlines import Redlines
from .utils.conversion_manager import ConversionManager
from .utils.styles import Styles


class RedlinesAPI:
    """Factory for FastAPI routes exposing Redlines functionality."""

    def __init__(
        self,
        *,
        styles: Styles | None = None,
        conversion_manager: ConversionManager | None = None,
        router_prefix: str = '/redlines',
    ) -> None:
        self.styles = styles or Styles()
        self.conversion_manager = conversion_manager or ConversionManager(styles=self.styles)
        self.router = APIRouter(prefix=router_prefix, tags=['redlines'])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route('/health', self.health, methods=['GET'], response_model=HealthResponse)
        self.router.add_api_route('/diff', self.create_diff, methods=['POST'], response_model=DiffResponse)
        self.router.add_api_route('/convert', self.convert_payload, methods=['POST'], response_model=ConvertResponse)

    def create_app(self) -> FastAPI:
        """Return a stand-alone :class:`FastAPI` application mounting the router."""
        app = FastAPI(title='Redlines API', version=self._library_version())
        app.include_router(self.router)
        return app

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------
    def health(self) -> HealthResponse:
        return HealthResponse(version=self._library_version())

    def create_diff(self, request: DiffRequest) -> DiffResponse:
        options: dict[str, Any] = dict(request.options)
        if request.markdown_style:
            options.setdefault('markdown_style', request.markdown_style)
        if request.source_format:
            options.setdefault('source_format', request.source_format)
        if request.test_format:
            options.setdefault('test_format', request.test_format)

        redlines = Redlines(
            request.source,
            request.test,
            styles=self.styles,
            conversion_manager=self.conversion_manager,
            **options,
        )

        try:
            payload = redlines.output_json
        except ValueError as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return DiffResponse.model_validate(payload)

    async def convert_payload(self, request: ConvertRequest) -> ConvertResponse:
        metadata = request.metadata or {}
        if request.target_format:
            result = await self.conversion_manager.convert(
                request.data,
                request.source_format,
                request.target_format,
                metadata=metadata,
            )
            target_format = request.target_format
        else:
            result = await self.conversion_manager.extract_text(request.data, request.source_format)
            target_format = 'txt'

        return ConvertResponse(result=result, source_format=request.source_format, target_format=target_format)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _library_version() -> str:
        try:
            return version('redlines')
        except PackageNotFoundError:  # pragma: no cover - local development fallback
            return '0.0.0-dev'


__all__ = ['RedlinesAPI']
