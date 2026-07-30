"""
session_cache.py
Memoria temporal para sesiones de recomendación de plantas.
Reemplaza los dicts sueltos session_recommendations_cache y session_cache_timestamps.
Thread-safe para uso con uvicorn single-worker.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 60  # Tiempo de vida de cada sesión


class SessionCache:
    def __init__(self, ttl_minutes: int = SESSION_TTL_MINUTES):
        self._store: Dict[str, dict] = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    def set_plants(self, session_id: str, plants: List[str]) -> None:
        """Guarda las plantas recomendadas para una sesión."""
        self._store[session_id] = {
            "plants": plants,
            "created_at": datetime.now(),
        }
        logger.info(f"💾 Cache SET [{session_id}]: {plants}")

    def get_plants(self, session_id: str) -> Optional[List[str]]:
        """Retorna plantas si la sesión existe y no expiró. Si expiró, la elimina."""
        entry = self._store.get(session_id)
        if not entry:
            logger.info(f"🔍 Cache MISS [{session_id}]")
            return None

        age = datetime.now() - entry["created_at"]
        if age > self.ttl:
            logger.info(f"⏰ Cache EXPIRED [{session_id}] (age={age})")
            self._delete(session_id)
            return None

        logger.info(f"✅ Cache HIT [{session_id}]: {entry['plants']}")
        return entry["plants"]

    def _delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Elimina todas las sesiones expiradas. Retorna cantidad eliminada."""
        now = datetime.now()
        expired = [
            sid for sid, entry in self._store.items()
            if now - entry["created_at"] > self.ttl
        ]
        for sid in expired:
            self._delete(sid)
        if expired:
            logger.info(f"🧹 Cache cleanup: {len(expired)} sesiones eliminadas")
        return len(expired)

    def debug_info(self, session_id: str) -> dict:
        """Info de debug para el endpoint /debug-session."""
        entry = self._store.get(session_id)
        all_sessions = list(self._store.keys())
        if not entry:
            return {
                "session_id": session_id,
                "cached_plants": [],
                "cache_timestamp": None,
                "age_seconds": None,
                "expired": None,
                "cache_size": len(self._store),
                "all_sessions": all_sessions,
            }
        age = datetime.now() - entry["created_at"]
        return {
            "session_id": session_id,
            "cached_plants": entry["plants"],
            "cache_timestamp": entry["created_at"].isoformat(),
            "age_seconds": age.total_seconds(),
            "expired": age > self.ttl,
            "cache_size": len(self._store),
            "all_sessions": all_sessions,
        }


# Instancia global — importar esto en server.py
plant_session_cache = SessionCache()