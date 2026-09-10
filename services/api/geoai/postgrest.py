"""User-scoped Data API adapter. RLS is authoritative for every operation."""

from fastapi import HTTPException
import httpx
from .config import Settings


class PostgrestProjectRepository:
    def __init__(self, token: str):
        self.cfg = Settings()
        self.token = token

    def request(self, method, table, *, params=None, body=None):
        try:
            response = httpx.request(
                method,
                self.cfg.supabase_url + "/rest/v1/" + table,
                headers={
                    "apikey": self.cfg.anon_key.get_secret_value(),
                    "Authorization": "Bearer " + self.token,
                    "Prefer": "return=representation",
                },
                params=params,
                json=body,
                timeout=15,
            )
        except httpx.HTTPError:
            raise HTTPException(503, "Data service unavailable") from None
        if response.status_code >= 400:
            status = response.status_code
            if status == 401:
                raise HTTPException(401, "Session expired")
            if status == 403:
                raise HTTPException(403, "Permission denied")
            if status in (400, 404, 409, 422):
                raise HTTPException(400, "Invalid data or existing member")
            raise HTTPException(503, "Data service unavailable")
        return response.json() if response.content else []

    def list_for_user(self, user_id):
        # user_id is verified at the service boundary; JWT + RLS scope the query.
        return self.request("GET", "projects", params={"order": "created_at.desc"})

    def get(self, project_id, user_id):
        rows = self.request("GET", "projects", params={"id": "eq." + str(project_id)})
        return rows[0] if rows else None

    def create(self, data, user_id):
        return self.request("POST", "projects", body={**data, "owner_id": str(user_id)})[0]

    def update(self, project_id, data):
        rows = self.request("PATCH", "projects", params={"id": "eq." + str(project_id)}, body=data)
        if not rows:
            raise HTTPException(403, "Permission denied")
        return rows[0]

    def members(self, project_id):
        return self.request(
            "GET",
            "project_members",
            params={"project_id": "eq." + str(project_id), "order": "created_at.asc"},
        )

    def add_member(self, project_id, data):
        return self.request(
            "POST", "project_members", body={**data, "project_id": str(project_id)}
        )[0]

    def change_member(self, project_id, user_id, role):
        rows = self.request(
            "PATCH",
            "project_members",
            params={"project_id": "eq." + str(project_id), "user_id": "eq." + str(user_id)},
            body={"role": role},
        )
        if not rows:
            raise HTTPException(403, "Permission denied")
        return rows[0]

    def remove_member(self, project_id, user_id):
        rows = self.request(
            "DELETE",
            "project_members",
            params={"project_id": "eq." + str(project_id), "user_id": "eq." + str(user_id)},
        )
        if not rows:
            raise HTTPException(403, "Permission denied")
