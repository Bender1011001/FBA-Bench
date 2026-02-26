from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .state import experiment_configs_db, simulation_configs_db, templates_db

logger = logging.getLogger(__name__)


class ConfigPersistenceManager:
    def __init__(self, config_dir: str = "./config_storage"):
        self.config_dir = config_dir
        self.experiments_dir = os.path.join(config_dir, "experiments")
        self.templates_dir = os.path.join(config_dir, "templates")
        self.simulations_dir = os.path.join(config_dir, "simulations")
        os.makedirs(self.experiments_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.simulations_dir, exist_ok=True)
        logger.info("ConfigPersistenceManager storage: %s", config_dir)

    # ---- Experiments ----
    def save_experiment_config(
        self, experiment_id: str, config_data: Dict[str, Any]
    ) -> bool:
        try:
            file_path = os.path.join(self.experiments_dir, f"{experiment_id}.json")
            now = datetime.now().isoformat()
            with open(file_path, "w") as f:
                json.dump(
                    {
                        "experiment_id": experiment_id,
                        "config_data": config_data,
                        "created_at": now,
                        "updated_at": now,
                    },
                    f,
                    indent=2,
                )
            experiment_configs_db[experiment_id] = config_data
            return True
        except Exception as e:
            logger.exception("save_experiment_config failed: %s", e)
            return False

    def load_experiment_config(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        try:
            p = os.path.join(self.experiments_dir, f"{experiment_id}.json")
            if not os.path.exists(p):
                return None
            with open(p) as f:
                data = json.load(f)
            experiment_configs_db[experiment_id] = data["config_data"]
            return data["config_data"]
        except Exception as e:
            logger.exception("load_experiment_config failed: %s", e)
            return None

    def delete_experiment_config(self, experiment_id: str) -> bool:
        try:
            p = os.path.join(self.experiments_dir, f"{experiment_id}.json")
            if os.path.exists(p):
                os.remove(p)
            experiment_configs_db.pop(experiment_id, None)
            return True
        except Exception as e:
            logger.exception("delete_experiment_config failed: %s", e)
            return False

    def list_experiment_configs(self) -> List[str]:
        try:
            return [
                f[:-5] for f in os.listdir(self.experiments_dir) if f.endswith(".json")
            ]
        except Exception as e:
            logger.exception("list_experiment_configs failed: %s", e)
            return []

    # ---- Templates ----
    def save_template(self, template_name: str, template_data: Dict[str, Any]) -> bool:
        try:
            p = os.path.join(self.templates_dir, f"{template_name}.json")
            now = datetime.now().isoformat()
            with open(p, "w") as f:
                json.dump(
                    {**template_data, "created_at": now, "updated_at": now}, f, indent=2
                )
            templates_db[template_name] = template_data
            return True
        except Exception as e:
            logger.exception("save_template failed: %s", e)
            return False

    def load_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        try:
            p = os.path.join(self.templates_dir, f"{template_name}.json")
            if not os.path.exists(p):
                return None
            with open(p) as f:
                data = json.load(f)
            templates_db[template_name] = data
            return data
        except Exception as e:
            logger.exception("load_template failed: %s", e)
            return None

    def delete_template(self, template_name: str) -> bool:
        try:
            p = os.path.join(self.templates_dir, f"{template_name}.json")
            if os.path.exists(p):
                os.remove(p)
            templates_db.pop(template_name, None)
            return True
        except Exception as e:
            logger.exception("delete_template failed: %s", e)
            return False

    def list_templates(self) -> List[str]:
        try:
            return [
                f[:-5] for f in os.listdir(self.templates_dir) if f.endswith(".json")
            ]
        except Exception as e:
            logger.exception("list_templates failed: %s", e)
            return []

    # ---- Simulations ----
    def save_simulation_config(
        self, config_id: str, config_data: Dict[str, Any]
    ) -> bool:
        try:
            p = os.path.join(self.simulations_dir, f"{config_id}.json")
            now = datetime.now().isoformat()
            with open(p, "w") as f:
                json.dump(
                    {
                        "config_id": config_id,
                        "config_data": config_data,
                        "created_at": now,
                        "updated_at": now,
                    },
                    f,
                    indent=2,
                )
            simulation_configs_db[config_id] = config_data
            return True
        except Exception as e:
            logger.exception("save_simulation_config failed: %s", e)
            return False

    def load_simulation_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        try:
            p = os.path.join(self.simulations_dir, f"{config_id}.json")
            if not os.path.exists(p):
                return None
            with open(p) as f:
                data = json.load(f)
            simulation_configs_db[config_id] = data["config_data"]
            return data["config_data"]
        except Exception as e:
            logger.exception("load_simulation_config failed: %s", e)
            return None

    def delete_simulation_config(self, config_id: str) -> bool:
        try:
            p = os.path.join(self.simulations_dir, f"{config_id}.json")
            if os.path.exists(p):
                os.remove(p)
            simulation_configs_db.pop(config_id, None)
            return True
        except Exception as e:
            logger.exception("delete_simulation_config failed: %s", e)
            return False

    def list_simulation_configs(self) -> List[str]:
        try:
            return [
                f[:-5] for f in os.listdir(self.simulations_dir) if f.endswith(".json")
            ]
        except Exception as e:
            logger.exception("list_simulation_configs failed: %s", e)
            return []

    def initialize_from_storage(self) -> None:
        for eid in self.list_experiment_configs():
            self.load_experiment_config(eid)
        for sid in self.list_simulation_configs():
            self.load_simulation_config(sid)
        for t in self.list_templates():
            self.load_template(t)


# Global instance (import where needed)
config_persistence_manager = ConfigPersistenceManager()

# ===================== SQLAlchemy-backed persistence for API resources =====================
from sqlalchemy.orm import Session  # noqa: E402

from fba_bench_api.models.agent import AgentORM  # noqa: E402
from fba_bench_api.models.base import utcnow  # noqa: E402
from fba_bench_api.models.experiment import ExperimentORM, ExperimentStatusEnum  # noqa: E402
from fba_bench_api.models.simulation import SimulationORM  # noqa: E402


class AgentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[dict]:
        return [a.to_dict() for a in self.db.query(AgentORM).all()]

    def create(self, data: dict) -> dict:
        obj = AgentORM(
            id=data["id"],
            name=data["name"],
            framework=data["framework"],
            config=data.get("config") or {},
        )
        self.db.add(obj)
        self.db.flush()
        return obj.to_dict()

    def get(self, agent_id: str) -> Optional[dict]:
        obj = self.db.get(AgentORM, agent_id)
        return obj.to_dict() if obj else None

    def update(self, agent_id: str, data: dict) -> Optional[dict]:
        obj = self.db.get(AgentORM, agent_id)
        if not obj:
            return None
        if "name" in data and data["name"] is not None:
            obj.name = data["name"]
        if "framework" in data and data["framework"] is not None:
            obj.framework = data["framework"]
        if "config" in data and data["config"] is not None:
            obj.config = data["config"]
        obj.updated_at = utcnow()
        self.db.flush()
        return obj.to_dict()

    def delete(self, agent_id: str) -> bool:
        obj = self.db.get(AgentORM, agent_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True


class ExperimentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[dict]:
        return [e.to_dict() for e in self.db.query(ExperimentORM).all()]

    def create(self, data: dict) -> dict:
        obj = ExperimentORM(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            agent_id=data["agent_id"],
            scenario_id=data.get("scenario_id"),
            params=data.get("params") or {},
            status=ExperimentStatusEnum.draft,
        )
        self.db.add(obj)
        self.db.flush()
        return obj.to_dict()

    def get(self, exp_id: str) -> Optional[dict]:
        obj = self.db.get(ExperimentORM, exp_id)
        return obj.to_dict() if obj else None

    def update(self, exp_id: str, data: dict) -> Optional[dict]:
        obj = self.db.get(ExperimentORM, exp_id)
        if not obj:
            return None
        if "name" in data and data["name"] is not None:
            obj.name = data["name"]
        if "description" in data:
            obj.description = data["description"]
        if "params" in data and data["params"] is not None:
            obj.params = data["params"]
        if "status" in data and data["status"] is not None:
            obj.status = ExperimentStatusEnum(data["status"])
        obj.updated_at = utcnow()
        self.db.flush()
        return obj.to_dict()

    def delete(self, exp_id: str) -> bool:
        obj = self.db.get(ExperimentORM, exp_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True


class SimulationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: dict) -> dict:
        obj = SimulationORM(
            id=data["id"],
            experiment_id=data.get("experiment_id"),
            # status defaults to pending
            sim_metadata=data.get("metadata") or {},
        )
        self.db.add(obj)
        self.db.flush()
        return obj.to_dict_with_topic()

    def get(self, sim_id: str) -> Optional[dict]:
        obj = self.db.get(SimulationORM, sim_id)
        return obj.to_dict_with_topic() if obj else None

    def update(self, sim_id: str, data: dict) -> Optional[dict]:
        obj = self.db.get(SimulationORM, sim_id)
        if not obj:
            return None
        # Only allow status and metadata updates here; routes validate transitions
        if "status" in data and data["status"] is not None:
            obj.status = data["status"]
        if "metadata" in data and data["metadata"] is not None:
            obj.sim_metadata = data["metadata"]
        obj.updated_at = utcnow()
        self.db.flush()
        return obj.to_dict_with_topic()


class PersistenceManager:
    """
    Provides typed repositories bound to a SQLAlchemy Session.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def agents(self) -> AgentRepository:
        return AgentRepository(self.db)

    def experiments(self) -> ExperimentRepository:
        return ExperimentRepository(self.db)

    def simulations(self) -> SimulationRepository:
        return SimulationRepository(self.db)
