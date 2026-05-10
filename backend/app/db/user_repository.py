# -*- coding: utf-8 -*-
"""
用户仓储
表：users
"""
import logging
from typing import Any, Dict, List, Optional
from app.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        role: str = "user",
    ) -> Dict[str, Any]:
        rows = self._execute_returning(
            """
            INSERT INTO users(username, password_hash, role)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (username, password_hash, role),
        )
        return self._normalize(rows[0]) if rows else {}

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,)
        )
        return self._normalize(rows[0]) if rows else None

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM users WHERE username = %s LIMIT 1", (username,)
        )
        return self._normalize(rows[0]) if rows else None

    def list_all(self) -> List[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM users ORDER BY created_at DESC"
        )
        return [self._normalize(r) for r in rows]

    def update_role(
        self,
        user_id: str,
        *,
        role: str,
    ) -> Optional[Dict[str, Any]]:
        self._execute_sql(
            "UPDATE users SET role = %s, updated_at = NOW() WHERE id = %s",
            (role, user_id)
        )
        return self.get_by_id(user_id)

    def delete(self, user_id: str) -> None:
        self._execute_sql("DELETE FROM users WHERE id = %s", (user_id,))

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "created_at": str(row["created_at"]) if row.get("created_at") else None,
            "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
        }


_instance: Optional[UserRepository] = None


def get_user_repository() -> UserRepository:
    global _instance
    if _instance is None:
        _instance = UserRepository()
    return _instance
