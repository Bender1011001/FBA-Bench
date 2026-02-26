from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List

import yaml
from fastapi import APIRouter

from fba_bench_api.models.template import Template, TemplateResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/", response_model=TemplateResponse)
async def get_templates() -> TemplateResponse:
    """
    Retrieve all template YAML files from the configs directory.
    Parses each file and returns structured template data.
    """
    configs_dir = Path("configs")
    if not configs_dir.exists():
        logger.warning("Configs directory does not exist: %s", configs_dir)
        return TemplateResponse(templates=[])

    templates: List[Template] = []
    yaml_files = list(configs_dir.glob("*.yaml")) + list(configs_dir.glob("*.yml"))

    for file_path in yaml_files:
        try:
            name = file_path.name
            relative_path = file_path.relative_to(Path.cwd())
            content = file_path.read_text(encoding="utf-8")
            parsed = yaml.safe_load(content) or {}
            stat = file_path.stat()
            size = stat.st_size
            modified_timestamp = datetime.fromtimestamp(
                stat.st_mtime, tz=datetime.UTC  # type: ignore[attr-defined]
            ).isoformat()

            template = Template(
                name=name,
                path=str(relative_path),
                content=content,
                parsed=parsed,
                size=size,
                modified=modified_timestamp,
            )
            templates.append(template)

        except yaml.YAMLError as e:
            logger.warning("Failed to parse YAML in %s: %s", file_path, e)
            # Continue with empty parsed
            parsed = {}
            # Reconstruct template with partial data
            try:
                stat = file_path.stat()
                templates.append(
                    Template(
                        name=file_path.name,
                        path=str(file_path.relative_to(Path.cwd())),
                        content=file_path.read_text(encoding="utf-8"),
                        parsed=parsed,
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(
                            stat.st_mtime, tz=datetime.UTC  # type: ignore[attr-defined]
                        ).isoformat(),
                    )
                )
            except Exception as read_e:
                logger.error("Failed to read file %s: %s", file_path, read_e)
        except Exception as e:
            logger.error("Error processing template file %s: %s", file_path, e)
            continue

    logger.info("Loaded %d templates from configs directory", len(templates))
    return TemplateResponse(templates=templates)


# Alias route without trailing slash to avoid 404/redirect issues when clients call "/api/v1/templates"
@router.get("", response_model=TemplateResponse, include_in_schema=False)
async def get_templates_noslash() -> TemplateResponse:
    return await get_templates()
