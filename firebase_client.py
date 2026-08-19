"""
firebase_client.py

Thin wrapper around the Firebase Realtime Database REST API.

Why REST instead of the firebase-admin SDK:
- No service account JSON file to distribute with the server/exe.
- Works with a simple Web API Key + Database Secret, which is easier
  for a hobby/self-hosted project to set up once and forget.
- Zero extra native dependencies -> easier to bundle with PyInstaller.

You need a real Firebase project for this to work (Firebase itself is
still a real Google service - "fakedomains" refers to the domain NAMES
being made up by users, not to Firebase being fake). Setup steps are in
README.md.
"""

from __future__ import annotations

import time
import requests
from typing import Any, Optional


class FirebaseError(Exception):
    pass


class FirebaseClient:
    def __init__(self, database_url: str, auth_secret: Optional[str] = None, timeout: float = 6.0):
        """
        database_url: e.g. "https://mavencraft-abc123-default-rtdb.firebaseio.com"
        auth_secret: the Realtime Database "secret" (legacy token) OR a
                     Firebase Auth ID token. Passed as ?auth= on every request.
                     Optional if your DB rules allow public read/write
                     (fine for prototyping, NOT recommended for real use).
        """
        self.database_url = database_url.rstrip("/")
        self.auth_secret = auth_secret
        self.timeout = timeout

    def _url(self, path: str) -> str:
        path = path.strip("/")
        url = f"{self.database_url}/{path}.json"
        if self.auth_secret:
            url += f"?auth={self.auth_secret}"
        return url

    def get(self, path: str) -> Any:
        try:
            resp = requests.get(self._url(path), timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise FirebaseError(f"GET {path} failed: {e}") from e

    def set(self, path: str, value: Any) -> Any:
        try:
            resp = requests.put(self._url(path), json=value, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise FirebaseError(f"SET {path} failed: {e}") from e

    def update(self, path: str, value: dict) -> Any:
        try:
            resp = requests.patch(self._url(path), json=value, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise FirebaseError(f"UPDATE {path} failed: {e}") from e

    def delete(self, path: str) -> None:
        try:
            resp = requests.delete(self._url(path), timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise FirebaseError(f"DELETE {path} failed: {e}") from e

    def domain_exists(self, domain_key: str) -> bool:
        result = self.get(f"domains/{domain_key}")
        return result is not None

    def register_domain(self, domain_key: str, record: dict) -> None:
        """Create/overwrite a domain record. Caller should check
        domain_exists() first if 'first come first served' matters,
        though there's an inherent race condition risk without a
        Firebase Transaction; see NOTE in server.py wizard."""
        self.set(f"domains/{domain_key}", record)

    def heartbeat(self, domain_key: str, players_online: int, alive: bool = True) -> None:
        self.update(f"domains/{domain_key}", {
            "players_online": players_online,
            "last_heartbeat": int(time.time()),
            "alive": alive,
        })

    def unregister_domain(self, domain_key: str) -> None:
        self.update(f"domains/{domain_key}", {"alive": False})

    def list_domains(self) -> dict:
        result = self.get("domains")
        return result or {}
