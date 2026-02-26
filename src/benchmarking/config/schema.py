# Deprecated module: benchmarking.config.schema
# This module has been fully deprecated in favor of Pydantic-based configuration models.
# Any import of this module must fail loudly to prevent accidental use.
raise ImportError(
    "benchmarking.config.schema is deprecated; import from benchmarking.config.pydantic_config instead."
)
