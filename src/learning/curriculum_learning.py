from __future__ import annotations

from typing import Any, Dict, Optional


class CurriculumLearning:
    """Tracks curriculum levels and per-student progress."""

    def __init__(self) -> None:
        self._curriculum: Dict[str, Dict[str, Any]] = {}
        self._student_progress: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def add_curriculum_level(self, level_data: Dict[str, Any]) -> str:
        level_id = str(level_data.get("level_id") or "")
        if not level_id:
            raise ValueError("level_id is required")
        self._curriculum[level_id] = dict(level_data)
        return level_id

    def get_curriculum_level(self, level_id: str) -> Optional[Dict[str, Any]]:
        return self._curriculum.get(level_id)

    def update_student_progress(self, progress_data: Dict[str, Any]) -> str:
        student_id = str(progress_data.get("student_id") or "")
        level_id = str(progress_data.get("level_id") or "")
        if not student_id or not level_id:
            raise ValueError("student_id and level_id are required")
        self._student_progress.setdefault(student_id, {})[level_id] = dict(
            progress_data
        )
        return f"{student_id}:{level_id}"

    def get_next_level(self, student_id: str) -> Optional[Dict[str, Any]]:
        completed = set(self._student_progress.get(student_id, {}).keys())
        # Choose the lowest difficulty level that is not completed and whose prerequisites are met.
        candidates = sorted(
            self._curriculum.values(),
            key=lambda d: (int(d.get("difficulty", 0)), str(d.get("level_id", ""))),
        )
        for lvl in candidates:
            lid = str(lvl.get("level_id") or "")
            if not lid or lid in completed:
                continue
            prereqs = lvl.get("prerequisites") or []
            prereq_ids = {str(p) for p in prereqs if p}
            if prereq_ids.issubset(completed):
                return lvl
        return None

    def get_student_progress(self, student_id: str) -> Dict[str, Dict[str, Any]]:
        return dict(self._student_progress.get(student_id, {}))
