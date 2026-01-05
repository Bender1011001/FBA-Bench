from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError


class LLMConfig(BaseModel):
    """Configuration for the LLM client used by the agent."""
    client_type: Literal["openrouter"] = Field(
        ...,
        description="The type of LLM client to use",
        examples=["openrouter"]
    )
    model: str = Field(
        ...,
        min_length=3,
        description="The specific LLM model identifier",
        examples=["xai/grok-1.5-flash"]
    )
    temperature: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Sampling temperature for LLM generation (0.0 to 1.0)",
        examples=[0.6]
    )
    max_tokens: int = Field(
        ...,
        ge=64,
        le=4096,
        description="Maximum number of tokens to generate",
        examples=[2000]
    )

class AgentConfig(BaseModel):
    """Core configuration for an individual agent."""
    name: str = Field(
        ...,
        description="Human-readable name of the agent",
        examples=["Grok-4 Bot"]
    )
    description: str = Field(
        ...,
        description="Detailed description of the agent's purpose and behavior",
        examples=["A baseline agent powered by xAI's Grok-4 model via OpenRouter."]
    )
    agent_class: str = Field(
        ...,
        description="The Python class path for instantiating the agent",
        examples=["benchmarking.agents.unified_agent.UnifiedAgent"]
    )
    llm_config: LLMConfig = Field(
        ...,
        description="LLM-specific configuration for the agent"
    )

class Genome(BaseModel):
    """Complete genome structure representing an evolved agent configuration."""
    agent: AgentConfig = Field(
        ...,
        description="The agent configuration within this genome"
    )

def validate_genome_yaml(yaml_content: str) -> Genome:
    """
    Validate a YAML string representing a genome configuration.
    
    Args:
        yaml_content: The YAML string to validate.
    
    Returns:
        Genome: A validated Pydantic Genome model instance.
    
    Raises:
        ValidationError: If the YAML structure or values are invalid, with detailed error messages.
        yaml.YAMLError: If the YAML parsing fails.
    """
    try:
        parsed = yaml.safe_load(yaml_content)
        if parsed is None:
            raise ValueError("YAML content is empty or None")
        validated = Genome(**parsed)
        return validated
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML format: {str(e)}") from e
    except ValidationError as e:
        error_msg = "Genome validation failed. Common issues:\n"
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_msg += f"- {field}: {msg}\n"
        raise ValidationError(error_msg, __cause__=e) from e
    except Exception as e:
        raise ValueError(f"Unexpected error during validation: {str(e)}") from e

# Example usage (for documentation; not executed)
# yaml_str = """
# agent:
#   name: "Test Agent"
#   description: "Test description"
#   agent_class: "test.agent.TestAgent"
#   llm_config:
#     client_type: "openrouter"
#     model: "test/model"
#     temperature: 0.7
#     max_tokens: 1000
# """
# genome = validate_genome_yaml(yaml_str)
