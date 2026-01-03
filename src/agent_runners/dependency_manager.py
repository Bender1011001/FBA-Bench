"""
Dependency Manager - Handles optional framework dependencies for agent runners.

This module provides utilities for checking framework availability,
installing missing dependencies, and graceful fallbacks.
"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FrameworkDependency:
    """Information about a framework's dependencies."""

    name: str
    import_name: str
    install_package: str
    version_check: Optional[str] = None
    optional_extras: List[str] = None

    def __post_init__(self):
        if self.optional_extras is None:
            self.optional_extras = []


class DependencyManager:
    """
    Manager for framework dependencies and availability checking.

    Provides utilities for:
    - Checking if frameworks are available
    - Installing missing dependencies
    - Getting framework information
    - Graceful fallback handling
    """

    # Framework dependency definitions
    FRAMEWORK_DEPENDENCIES = {
        "crewai": FrameworkDependency(
            name="CrewAI",
            import_name="crewai",
            install_package="crewai>=0.28.0",
            optional_extras=["crewai-tools>=0.2.0"],
        ),
        "langchain": FrameworkDependency(
            name="LangChain",
            import_name="langchain",
            install_package="langchain>=0.1.0",
            optional_extras=[
                "langchain-community>=0.0.20",
                "langchain-openai>=0.0.5",
                "langchain-anthropic>=0.1.0",
            ],
        ),
        "openai": FrameworkDependency(
            name="OpenAI", import_name="openai", install_package="openai>=1.12.0"
        ),
        "anthropic": FrameworkDependency(
            name="Anthropic",
            import_name="anthropic",
            install_package="anthropic>=0.8.0",
        ),
    }

    def __init__(self):
        self._availability_cache: Dict[str, bool] = {}
        self._version_cache: Dict[str, str] = {}

    def check_framework_availability(self, framework: str) -> bool:
        """
        Check if a framework is available for use.

        Args:
            framework: Framework name (e.g., 'crewai', 'langchain')

        Returns:
            True if framework is available, False otherwise
        """
        if framework in self._availability_cache:
            return self._availability_cache[framework]

        if framework not in self.FRAMEWORK_DEPENDENCIES:
            logger.warning(f"Unknown framework: {framework}")
            return False

        dependency = self.FRAMEWORK_DEPENDENCIES[framework]

        try:
            # Try to import the main module
            import_module(dependency.import_name)
            self._availability_cache[framework] = True
            logger.debug(f"Framework {framework} is available")
            return True

        except ImportError as e:
            self._availability_cache[framework] = False
            logger.debug(f"Framework {framework} not available: {e}")
            return False

    def get_framework_version(self, framework: str) -> Optional[str]:
        """
        Get the version of an installed framework.

        Args:
            framework: Framework name

        Returns:
            Version string if available, None otherwise
        """
        if framework in self._version_cache:
            return self._version_cache[framework]

        if not self.check_framework_availability(framework):
            return None

        dependency = self.FRAMEWORK_DEPENDENCIES[framework]

        try:
            module = import_module(dependency.import_name)
            version = getattr(module, "__version__", None)
            if version:
                self._version_cache[framework] = version
                return version
        except (ImportError, AttributeError):
            pass

        return None

    def get_available_frameworks(self) -> List[str]:
        """Get list of available framework names."""
        available = []
        for framework in self.FRAMEWORK_DEPENDENCIES:
            if self.check_framework_availability(framework):
                available.append(framework)
        return available

    def get_missing_frameworks(self) -> List[str]:
        """Get list of frameworks that are not available."""
        missing = []
        for framework in self.FRAMEWORK_DEPENDENCIES:
            if not self.check_framework_availability(framework):
                missing.append(framework)
        return missing

    def get_framework_info(self, framework: str) -> Dict[str, Any]:
        """
        Get detailed information about a framework.

        Args:
            framework: Framework name

        Returns:
            Dictionary with framework information
        """
        if framework not in self.FRAMEWORK_DEPENDENCIES:
            raise ValueError(f"Unknown framework: {framework}")

        dependency = self.FRAMEWORK_DEPENDENCIES[framework]
        available = self.check_framework_availability(framework)
        version = self.get_framework_version(framework) if available else None

        return {
            "name": dependency.name,
            "framework_key": framework,
            "import_name": dependency.import_name,
            "install_package": dependency.install_package,
            "optional_extras": dependency.optional_extras,
            "available": available,
            "version": version,
            "install_command": self._get_install_command(framework),
        }

    def get_all_framework_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all known frameworks."""
        return {
            framework: self.get_framework_info(framework)
            for framework in self.FRAMEWORK_DEPENDENCIES
        }

    def _get_install_command(self, framework: str) -> str:
        """Get pip install command for a framework."""
        if framework not in self.FRAMEWORK_DEPENDENCIES:
            return ""

        dependency = self.FRAMEWORK_DEPENDENCIES[framework]
        packages = [dependency.install_package] + dependency.optional_extras
        return f"pip install {' '.join(packages)}"

    def install_framework(self, framework: str, include_extras: bool = True) -> bool:
        """
        Install a framework using pip.

        Args:
            framework: Framework name to install
            include_extras: Whether to install optional extras

        Returns:
            True if installation succeeded, False otherwise
        """
        if framework not in self.FRAMEWORK_DEPENDENCIES:
            logger.error(f"Unknown framework: {framework}")
            return False

        dependency = self.FRAMEWORK_DEPENDENCIES[framework]
        packages = [dependency.install_package]

        if include_extras:
            packages.extend(dependency.optional_extras)

        try:
            logger.info(f"Installing {framework}: {' '.join(packages)}")

            # Run pip install
            cmd = [sys.executable, "-m", "pip", "install"] + packages
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Clear cache to force re-check
            self._availability_cache.pop(framework, None)
            self._version_cache.pop(framework, None)

            # Verify installation
            if self.check_framework_availability(framework):
                logger.info(f"Successfully installed {framework}")
                return True
            else:
                logger.error(f"Installation of {framework} succeeded but import failed")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install {framework}: {e}")
            logger.error(f"stderr: {e.stderr}")
            return False
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Unexpected error installing {framework}: {e}")
            return False

    def install_all_frameworks(self, include_extras: bool = True) -> Dict[str, bool]:
        """
        Install all frameworks.

        Args:
            include_extras: Whether to install optional extras

        Returns:
            Dictionary mapping framework names to installation success
        """
        results = {}
        for framework in self.FRAMEWORK_DEPENDENCIES:
            if not self.check_framework_availability(framework):
                results[framework] = self.install_framework(framework, include_extras)
            else:
                results[framework] = True  # Already available
        return results

    def clear_cache(self) -> None:
        """Clear the availability and version caches."""
        self._availability_cache.clear()
        self._version_cache.clear()

    def validate_framework_installation(self, framework: str) -> Tuple[bool, List[str]]:
        """
        Validate that a framework is properly installed.

        Args:
            framework: Framework name to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if framework not in self.FRAMEWORK_DEPENDENCIES:
            issues.append(f"Unknown framework: {framework}")
            return False, issues

        # Check main import
        if not self.check_framework_availability(framework):
            issues.append(f"Main module '{framework}' cannot be imported")
            return False, issues

        dependency = self.FRAMEWORK_DEPENDENCIES[framework]

        # Check optional imports for extras
        for extra in dependency.optional_extras:
            extra_name = extra.split(">=")[0].split("==")[0]  # Extract package name
            try:
                import_module(
                    extra_name.replace("-", "_")
                )  # Convert package name to module name
            except ImportError:
                issues.append(f"Optional dependency '{extra_name}' not available")

        # Framework-specific validations
        if framework == "crewai":
            issues.extend(self._validate_crewai())
        elif framework == "langchain":
            issues.extend(self._validate_langchain())

        return len(issues) == 0, issues

    def _validate_crewai(self) -> List[str]:
        """Validate CrewAI specific requirements."""
        issues = []
        try:
            from crewai import Agent, Crew, Task  # type: ignore[import-not-found]

            # Try to create a minimal crew to test functionality
        except ImportError as e:
            issues.append(f"CrewAI components not available: {e}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            issues.append(f"CrewAI validation error: {e}")
        return issues

    def _validate_langchain(self) -> List[str]:
        """Validate LangChain specific requirements."""
        issues = []
        try:
            from langchain.agents import AgentExecutor
            from langchain.tools import BaseTool

            # Basic LangChain components should be available
        except ImportError as e:
            issues.append(f"LangChain components not available: {e}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            issues.append(f"LangChain validation error: {e}")
        return issues

    def get_installation_guide(self) -> str:
        """Get a user-friendly installation guide."""
        guide = """
Framework Installation Guide for FBA-Bench Agent Runners

To use different agent frameworks, you need to install their dependencies:

1. Install all frameworks at once:
   pip install -r requirements-frameworks.txt

2. Install individual frameworks:

   CrewAI (Multi-agent collaboration):
   pip install crewai>=0.28.0 crewai-tools>=0.2.0

   LangChain (Reasoning chains and tools):
   pip install langchain>=0.1.0 langchain-community>=0.0.20 langchain-openai>=0.0.5

   LLM Providers (for model access):
   pip install openai>=1.12.0 anthropic>=0.8.0

3. Check installation:
   python -c "from agent_runners.dependency_manager import DependencyManager; print(DependencyManager().get_available_frameworks())"

Note: FBA-Bench works without these frameworks using the built-in DIY runner.
Optional frameworks enable advanced multi-agent capabilities.
"""

        return guide.strip()


# Global instance for convenience
dependency_manager = DependencyManager()


def check_framework_availability(framework: str) -> bool:
    """Convenience function to check framework availability."""
    return dependency_manager.check_framework_availability(framework)


def get_available_frameworks() -> List[str]:
    """Convenience function to get available frameworks."""
    return dependency_manager.get_available_frameworks()


def install_framework(framework: str) -> bool:
    """Convenience function to install a framework."""
    return dependency_manager.install_framework(framework)
