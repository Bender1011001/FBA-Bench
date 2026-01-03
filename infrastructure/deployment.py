"""
Infrastructure deployment module for FBA-Bench.

This module provides deployment utilities and configurations for running FBA-Bench
in different environments (development, staging, production).
"""

import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class DeploymentEnvironment(Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentType(Enum):
    """Supported deployment types."""

    DOCKER_COMPOSE = "docker_compose"
    KUBERNETES = "kubernetes"
    LOCAL = "local"


@dataclass
class DeploymentConfig:
    """Configuration for deployment."""

    environment: DeploymentEnvironment
    deployment_type: DeploymentType
    project_name: str = "fba-bench"
    docker_image_tag: str = "latest"
    docker_registry: Optional[str] = None
    kubernetes_namespace: str = "fba-bench"
    kubernetes_config_path: Optional[str] = None
    host_port: int = 8000
    container_port: int = 8000
    replicas: int = 1
    resources: Dict[str, Any] = field(default_factory=dict)
    # Back-compat: accept resource_limits at top-level and merge into resources['limits'] via __post_init__
    resource_limits: Optional[Dict[str, Any]] = None
    # Optional scalability settings; supports either dict or ScalabilityConfig (forward-ref)
    scaling_config: Optional[Union[Dict[str, Any], "ScalabilityConfig"]] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    volumes: List[Dict[str, str]] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    health_check: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "environment": self.environment.value,
            "deployment_type": self.deployment_type.value,
            "project_name": self.project_name,
            "docker_image_tag": self.docker_image_tag,
            "docker_registry": self.docker_registry,
            "kubernetes_namespace": self.kubernetes_namespace,
            "kubernetes_config_path": self.kubernetes_config_path,
            "host_port": self.host_port,
            "container_port": self.container_port,
            "replicas": self.replicas,
            "resources": self.resources,
            "resource_limits": self.resource_limits
            if self.resource_limits is not None
            else self.resources.get("limits"),
            "scaling_config": (
                self.scaling_config
                if isinstance(self.scaling_config, dict)
                else (asdict(self.scaling_config) if self.scaling_config is not None else None)
            ),
            "env_vars": self.env_vars,
            "volumes": self.volumes,
            "networks": self.networks,
            "depends_on": self.depends_on,
            "health_check": self.health_check,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeploymentConfig":
        """Create from dictionary."""
        return cls(
            environment=DeploymentEnvironment(data.get("environment", "development")),
            deployment_type=DeploymentType(data.get("deployment_type", "local")),
            project_name=data.get("project_name", "fba-bench"),
            docker_image_tag=data.get("docker_image_tag", "latest"),
            docker_registry=data.get("docker_registry"),
            kubernetes_namespace=data.get("kubernetes_namespace", "fba-bench"),
            kubernetes_config_path=data.get("kubernetes_config_path"),
            host_port=data.get("host_port", 8000),
            container_port=data.get("container_port", 8000),
            replicas=data.get("replicas", 1),
            resources=data.get("resources", {}),
            resource_limits=data.get("resource_limits"),
            scaling_config=data.get("scaling_config"),
            env_vars=data.get("env_vars", {}),
            volumes=data.get("volumes", []),
            networks=data.get("networks", []),
            depends_on=data.get("depends_on", []),
            health_check=data.get("health_check"),
        )

    def __post_init__(self) -> None:
        """
        Back-compat: if resource_limits is provided, merge it into resources['limits'].
        Accepts keys like cpu, memory, gpus. Existing limits take precedence unless overridden.
        """
        try:
            if self.resource_limits:
                if not isinstance(self.resources, dict):
                    self.resources = {}
                existing_limits = (
                    self.resources.get("limits", {})
                    if isinstance(self.resources.get("limits", {}), dict)
                    else {}
                )
                merged = dict(existing_limits)
                merged.update(dict(self.resource_limits))
                self.resources["limits"] = merged
        except Exception:
            # Keep object usable even if malformed inputs are provided
            pass


class DeploymentManager:
    """
    Manages deployment of FBA-Bench in different environments.

    This class provides methods to deploy, update, and manage FBA-Bench
    instances across different environments and deployment types.
    """

    def __init__(self, config: DeploymentConfig):
        """Initialize the deployment manager."""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.docker_compose_file = self.project_root / "docker-compose.yml"
        self.dockerfile = self.project_root / "Dockerfile"
        self.nginx_config = self.project_root / "nginx.conf"

        # Set default resource limits based on environment
        if not self.config.resources:
            self._set_default_resources()

        # Set default health check
        if not self.config.health_check:
            self.config.health_check = {
                "test": [
                    "CMD",
                    "curl",
                    "-f",
                    f"http://localhost:{self.config.container_port}/health",
                ],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "40s",
            }

        logger.info(f"DeploymentManager initialized for {config.environment.value} environment")

    def _set_default_resources(self) -> None:
        """Set default resource limits based on environment."""
        if self.config.environment == DeploymentEnvironment.DEVELOPMENT:
            self.config.resources = {
                "limits": {"memory": "2Gi", "cpu": "1"},
                "requests": {"memory": "1Gi", "cpu": "0.5"},
            }
        elif self.config.environment == DeploymentEnvironment.STAGING:
            self.config.resources = {
                "limits": {"memory": "4Gi", "cpu": "2"},
                "requests": {"memory": "2Gi", "cpu": "1"},
            }
        elif self.config.environment == DeploymentEnvironment.PRODUCTION:
            self.config.resources = {
                "limits": {"memory": "8Gi", "cpu": "4"},
                "requests": {"memory": "4Gi", "cpu": "2"},
            }

    def deploy(self) -> bool:
        """
        Deploy FBA-Bench based on the configuration.

        Returns:
            bool: True if deployment was successful, False otherwise.
        """
        logger.info(f"Starting deployment for {self.config.environment.value} environment")

        try:
            if self.config.deployment_type == DeploymentType.DOCKER_COMPOSE:
                return self._deploy_docker_compose()
            elif self.config.deployment_type == DeploymentType.KUBERNETES:
                return self._deploy_kubernetes()
            elif self.config.deployment_type == DeploymentType.LOCAL:
                return self._deploy_local()
            else:
                logger.error(f"Unsupported deployment type: {self.config.deployment_type}")
                return False
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def _deploy_docker_compose(self) -> bool:
        """Deploy using Docker Compose."""
        logger.info("Deploying with Docker Compose")

        # Generate docker-compose.override.yml with environment-specific settings
        override_file = self.project_root / "docker-compose.override.yml"
        self._generate_docker_compose_override(override_file)

        # Build and start services
        cmd = [
            "docker-compose",
            "-f",
            str(self.docker_compose_file),
            "-f",
            str(override_file),
            "-p",
            self.config.project_name,
            "up",
            "-d",
            "--build",
        ]

        try:
            # Fix #84: Use check=True for robust error handling
            subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True, check=True)
            logger.info("Docker Compose deployment successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker Compose deployment failed: {e.stderr}")
            return False

    def _deploy_kubernetes(self) -> bool:
        """Deploy using Kubernetes."""
        logger.info("Deploying with Kubernetes")

        # Check if kubectl is available
        if not shutil.which("kubectl"):
            logger.error("kubectl is not available in PATH")
            return False

        # Generate Kubernetes manifests
        k8s_dir = self.project_root / "k8s"
        k8s_dir.mkdir(exist_ok=True)

        self._generate_kubernetes_manifests(k8s_dir)

        # Apply manifests
        cmd = ["kubectl", "apply", "-f", str(k8s_dir), "-n", self.config.kubernetes_namespace]

        try:
            # Create namespace if it doesn't exist
            namespace_cmd = [
                "kubectl",
                "create",
                "namespace",
                self.config.kubernetes_namespace,
                "--dry-run=client",
                "-o",
                "yaml",
            ]
            result = subprocess.run(namespace_cmd, capture_output=True, text=True, check=True)
            
            apply_ns_cmd = ["kubectl", "apply", "-f", "-"]
            subprocess.run(apply_ns_cmd, input=result.stdout, text=True, check=True)

            # Apply manifests
            cmd = ["kubectl", "apply", "-f", str(k8s_dir), "-n", self.config.kubernetes_namespace]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.info("Kubernetes deployment successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Kubernetes deployment failed: {e.stderr}")
            return False

    def _deploy_local(self) -> bool:
        """Deploy locally."""
        logger.info("Deploying locally")

        # Check if required dependencies are available
        if not shutil.which("python3"):
            logger.error("python3 is not available in PATH")
            return False

        # Install dependencies if needed
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            cmd = ["pip3", "install", "-r", str(requirements_file)]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install dependencies: {e.stderr}")
                return False

        # Start the application
        cmd = ["python3", "-m", "api_server"]

        # Run in background - Popen doesn't support check=True as it doesn't wait
        subprocess.Popen(cmd, cwd=self.project_root)

        logger.info("Local deployment successful")
        return True

    def _generate_docker_compose_override(self, override_file: Path) -> None:
        """Generate docker-compose.override.yml with environment-specific settings."""
        services = {
            "api": {
                "environment": self.config.env_vars,
                "ports": [f"{self.config.host_port}:{self.config.container_port}"],
                "deploy": {"resources": self.config.resources, "replicas": self.config.replicas},
                "healthcheck": self.config.health_check,
            }
        }

        if self.config.volumes:
            services["api"]["volumes"] = self.config.volumes

        if self.config.networks:
            services["api"]["networks"] = self.config.networks

        if self.config.depends_on:
            services["api"]["depends_on"] = self.config.depends_on

        compose_override = {"version": "3.8", "services": services}

        if self.config.networks:
            compose_override["networks"] = {
                network: {"driver": "bridge"} for network in self.config.networks
            }

        with open(override_file, "w") as f:
            yaml.dump(compose_override, f, default_flow_style=False)

    def _generate_kubernetes_manifests(self, k8s_dir: Path) -> None:
        """Generate Kubernetes manifests."""
        # Generate ConfigMap
        config_map = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{self.config.project_name}-config",
                "namespace": self.config.kubernetes_namespace,
            },
            "data": self.config.env_vars,
        }

        with open(k8s_dir / "configmap.yaml", "w") as f:
            yaml.dump(config_map, f, default_flow_style=False)

        # Generate Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": self.config.project_name,
                "namespace": self.config.kubernetes_namespace,
                "labels": {"app": self.config.project_name},
            },
            "spec": {
                "replicas": self.config.replicas,
                "selector": {"matchLabels": {"app": self.config.project_name}},
                "template": {
                    "metadata": {"labels": {"app": self.config.project_name}},
                    "spec": {
                        "containers": [
                            {
                                "name": self.config.project_name,
                                "image": f"{self.config.docker_registry or ''}{self.config.project_name}:{self.config.docker_image_tag}",
                                "ports": [{"containerPort": self.config.container_port}],
                                "env": [
                                    {
                                        "name": key,
                                        "valueFrom": {
                                            "configMapKeyRef": {
                                                "name": f"{self.config.project_name}-config",
                                                "key": key,
                                            }
                                        },
                                    }
                                    for key in self.config.env_vars.keys()
                                ],
                                "resources": self.config.resources,
                                "readinessProbe": self.config.health_check,
                                "livenessProbe": self.config.health_check,
                            }
                        ]
                    },
                },
            },
        }

        if self.config.volumes:
            deployment["spec"]["template"]["spec"]["volumes"] = []
            for volume in self.config.volumes:
                deployment["spec"]["template"]["spec"]["volumes"].append(
                    {
                        "name": volume.get("name", "volume"),
                        "persistentVolumeClaim": {"claimName": volume.get("claimName", "pvc")},
                    }
                )
                deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = [
                    {
                        "name": volume.get("name", "volume"),
                        "mountPath": volume.get("mountPath", "/data"),
                    }
                ]

        with open(k8s_dir / "deployment.yaml", "w") as f:
            yaml.dump(deployment, f, default_flow_style=False)

        # Generate Service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.config.project_name,
                "namespace": self.config.kubernetes_namespace,
            },
            "spec": {
                "selector": {"app": self.config.project_name},
                "ports": [
                    {"protocol": "TCP", "port": 80, "targetPort": self.config.container_port}
                ],
                "type": "LoadBalancer",
            },
        }

        with open(k8s_dir / "service.yaml", "w") as f:
            yaml.dump(service, f, default_flow_style=False)

    def update(self) -> bool:
        """
        Update an existing deployment.

        Returns:
            bool: True if update was successful, False otherwise.
        """
        logger.info(f"Updating deployment for {self.config.environment.value} environment")

        try:
            if self.config.deployment_type == DeploymentType.DOCKER_COMPOSE:
                return self._update_docker_compose()
            elif self.config.deployment_type == DeploymentType.KUBERNETES:
                return self._update_kubernetes()
            elif self.config.deployment_type == DeploymentType.LOCAL:
                logger.info("Local deployment doesn't support updates. Please redeploy.")
                return False
            else:
                logger.error(f"Unsupported deployment type: {self.config.deployment_type}")
                return False
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False

    def _update_docker_compose(self) -> bool:
        """Update Docker Compose deployment."""
        logger.info("Updating Docker Compose deployment")

        # Generate docker-compose.override.yml with environment-specific settings
        override_file = self.project_root / "docker-compose.override.yml"
        self._generate_docker_compose_override(override_file)

        # Pull latest images and restart services
        cmd_pull = [
            "docker-compose",
            "-f",
            str(self.docker_compose_file),
            "-f",
            str(override_file),
            "-p",
            self.config.project_name,
            "pull",
        ]

        try:
            subprocess.run(cmd_pull, cwd=self.project_root, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker Compose pull failed: {e.stderr}")
            return False

        cmd_up = [
            "docker-compose",
            "-f",
            str(self.docker_compose_file),
            "-f",
            str(override_file),
            "-p",
            self.config.project_name,
            "up",
            "-d",
        ]

        try:
            subprocess.run(cmd_up, cwd=self.project_root, capture_output=True, text=True, check=True)
            logger.info("Docker Compose update successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker Compose update failed: {e.stderr}")
            return False

    def _update_kubernetes(self) -> bool:
        """Update Kubernetes deployment."""
        logger.info("Updating Kubernetes deployment")

        # Generate Kubernetes manifests
        k8s_dir = self.project_root / "k8s"
        k8s_dir.mkdir(exist_ok=True)

        self._generate_kubernetes_manifests(k8s_dir)

        try:
            # Apply manifests
            cmd_apply = ["kubectl", "apply", "-f", str(k8s_dir), "-n", self.config.kubernetes_namespace]
            subprocess.run(cmd_apply, capture_output=True, text=True, check=True)

            # Restart deployment
            cmd_restart = [
                "kubectl",
                "rollout",
                "restart",
                "deployment",
                self.config.project_name,
                "-n",
                self.config.kubernetes_namespace,
            ]
            subprocess.run(cmd_restart, capture_output=True, text=True, check=True)

            logger.info("Kubernetes update successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Kubernetes update failed: {e.stderr}")
            return False

    def stop(self) -> bool:
        """
        Stop the deployment.

        Returns:
            bool: True if stop was successful, False otherwise.
        """
        logger.info(f"Stopping deployment for {self.config.environment.value} environment")

        try:
            if self.config.deployment_type == DeploymentType.DOCKER_COMPOSE:
                return self._stop_docker_compose()
            elif self.config.deployment_type == DeploymentType.KUBERNETES:
                return self._stop_kubernetes()
            elif self.config.deployment_type == DeploymentType.LOCAL:
                return self._stop_local()
            else:
                logger.error(f"Unsupported deployment type: {self.config.deployment_type}")
                return False
        except Exception as e:
            logger.error(f"Stop failed: {e}")
            return False

    def _stop_docker_compose(self) -> bool:
        """Stop Docker Compose deployment."""
        logger.info("Stopping Docker Compose deployment")

        cmd = [
            "docker-compose",
            "-f",
            str(self.docker_compose_file),
            "-p",
            self.config.project_name,
            "down",
        ]

        try:
            subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True, check=True)
            logger.info("Docker Compose stop successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker Compose stop failed: {e.stderr}")
            return False

    def _stop_kubernetes(self) -> bool:
        """Stop Kubernetes deployment."""
        logger.info("Stopping Kubernetes deployment")

        try:
            cmd_delete_deploy = [
                "kubectl",
                "delete",
                "deployment",
                self.config.project_name,
                "-n",
                self.config.kubernetes_namespace,
            ]
            subprocess.run(cmd_delete_deploy, capture_output=True, text=True, check=True)

            cmd_delete_svc = [
                "kubectl",
                "delete",
                "service",
                self.config.project_name,
                "-n",
                self.config.kubernetes_namespace,
            ]
            subprocess.run(cmd_delete_svc, capture_output=True, text=True, check=True)

            logger.info("Kubernetes stop successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Kubernetes stop failed: {e.stderr}")
            return False

    def _stop_local(self) -> bool:
        """Stop local deployment using cross-platform process management."""
        logger.info("Stopping local deployment")

        try:
            import psutil
        except ImportError:
            logger.error("psutil is required for local deployment management. Install with: pip install psutil")
            return False

        # Find and terminate processes matching 'api_server' (cross-platform)
        terminated_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline) if cmdline else ''
                if 'api_server' in cmdline_str:
                    proc.terminate()
                    terminated_count += 1
                    logger.debug(f"Terminated process {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process already gone or we can't access it
                pass

        if terminated_count == 0:
            logger.info("No api_server processes found to stop")
        else:
            logger.info(f"Terminated {terminated_count} api_server process(es)")

        logger.info("Local stop successful")
        return True

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the deployment.

        Returns:
            Dict[str, Any]: Status information.
        """
        logger.info(f"Getting status for {self.config.environment.value} environment")

        try:
            if self.config.deployment_type == DeploymentType.DOCKER_COMPOSE:
                return self._status_docker_compose()
            elif self.config.deployment_type == DeploymentType.KUBERNETES:
                return self._status_kubernetes()
            elif self.config.deployment_type == DeploymentType.LOCAL:
                return self._status_local()
            else:
                logger.error(f"Unsupported deployment type: {self.config.deployment_type}")
                return {"error": f"Unsupported deployment type: {self.config.deployment_type}"}
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {"error": str(e)}

    def _status_docker_compose(self) -> Dict[str, Any]:
        """Get Docker Compose deployment status."""
        logger.info("Getting Docker Compose status")

        cmd = [
            "docker-compose",
            "-f",
            str(self.docker_compose_file),
            "-p",
            self.config.project_name,
            "ps",
        ]

        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)

        if result.returncode != 0:
            return {"error": result.stderr}

        # Parse output
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 1:
            return {"status": "No services running"}

        services = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3:
                services.append(
                    {
                        "name": parts[0],
                        "command": parts[1],
                        "state": parts[2],
                        "ports": parts[3] if len(parts) > 3 else "",
                    }
                )

        return {"status": "Running", "services": services}

    def _status_kubernetes(self) -> Dict[str, Any]:
        """Get Kubernetes deployment status."""
        logger.info("Getting Kubernetes status")

        # Get deployment status
        cmd = [
            "kubectl",
            "get",
            "deployment",
            self.config.project_name,
            "-n",
            self.config.kubernetes_namespace,
            "-o",
            "json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return {"error": result.stderr}

        deployment = json.loads(result.stdout)

        # Get pods status
        cmd = [
            "kubectl",
            "get",
            "pods",
            "-l",
            f"app={self.config.project_name}",
            "-n",
            self.config.kubernetes_namespace,
            "-o",
            "json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        pods = []
        if result.returncode == 0:
            pods_data = json.loads(result.stdout)
            for pod in pods_data.get("items", []):
                pods.append(
                    {
                        "name": pod["metadata"]["name"],
                        "status": pod["status"]["phase"],
                        "ready": pod["status"]
                        .get("containerStatuses", [{}])[0]
                        .get("ready", False),
                    }
                )

        return {
            "status": "Running",
            "deployment": {
                "name": deployment["metadata"]["name"],
                "replicas": deployment["spec"]["replicas"],
                "available_replicas": deployment["status"].get("availableReplicas", 0),
                "updated_replicas": deployment["status"].get("updatedReplicas", 0),
            },
            "pods": pods,
        }

    def _status_local(self) -> Dict[str, Any]:
        """Get local deployment status using cross-platform process management."""
        logger.info("Getting local status")

        try:
            import psutil
        except ImportError:
            logger.error("psutil is required for local deployment management. Install with: pip install psutil")
            return {"error": "psutil not installed"}

        # Find processes matching 'api_server' (cross-platform)
        pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline) if cmdline else ''
                if 'api_server' in cmdline_str:
                    pids.append(str(proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process already gone or we can't access it
                pass

        if not pids:
            return {"status": "Not running"}

        return {"status": "Running", "pids": pids}


def load_deployment_config(config_path: Union[str, Path]) -> DeploymentConfig:
    """
    Load deployment configuration from a file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        DeploymentConfig: The loaded configuration.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as f:
        data = json.load(f)

    return DeploymentConfig.from_dict(data)


def save_deployment_config(config: DeploymentConfig, config_path: Union[str, Path]) -> None:
    """
    Save deployment configuration to a file.

    Args:
        config: The configuration to save.
        config_path: Path to save the configuration file.
    """
    config_path = Path(config_path)

    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def create_default_config(environment: DeploymentEnvironment) -> DeploymentConfig:
    """
    Create a default deployment configuration for the specified environment.

    Args:
        environment: The deployment environment.

    Returns:
        DeploymentConfig: The default configuration.
    """
    if environment == DeploymentEnvironment.DEVELOPMENT:
        return DeploymentConfig(
            environment=environment,
            deployment_type=DeploymentType.LOCAL,
            env_vars={"DEBUG": "true", "LOG_LEVEL": "DEBUG"},
        )
    elif environment == DeploymentEnvironment.STAGING:
        return DeploymentConfig(
            environment=environment,
            deployment_type=DeploymentType.DOCKER_COMPOSE,
            replicas=2,
            env_vars={"DEBUG": "false", "LOG_LEVEL": "INFO"},
        )
    elif environment == DeploymentEnvironment.PRODUCTION:
        return DeploymentConfig(
            environment=environment,
            deployment_type=DeploymentType.KUBERNETES,
            replicas=3,
            env_vars={"DEBUG": "false", "LOG_LEVEL": "WARNING"},
        )
    else:
        raise ValueError(f"Unsupported environment: {environment}")


# Import yaml at the end to avoid circular imports
try:
    import yaml
except ImportError:
    logger.warning("PyYAML not available. Docker Compose and Kubernetes deployments will not work.")
    yaml = None
