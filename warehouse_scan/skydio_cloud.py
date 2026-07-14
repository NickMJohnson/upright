"""Minimal Skydio Cloud API client (the realistic Skydio-enterprise path).

The Cloud API is the ONLY public Skydio developer surface that fits this use
case without the access-gated real-time Control & Telemetry ICD. You cannot run
a custom onboard "barcode skill" on current Skydio hardware; instead the workable
architecture is:

    fly an autonomous mission  ->  Cloud API lists the flight & its media
                                ->  download the captured images/video
                                ->  run warehouse_scan.detector over them

Requires an enterprise org token. Generate one as an org admin at
https://cloud.skydio.com (Integrations), then set SKYDIO_API_TOKEN /
SKYDIO_API_TOKEN_ID (see .env.example). Endpoint shapes follow
https://apidocs.skydio.com — VERIFY exact paths/fields against the live docs for
your org, since the API evolves and some endpoints are versioned (v0/v1) or beta.

This is intentionally a thin, dependency-light stub: it shows the auth + request
pattern and gives you working `list_flights` / `download_media` calls to build on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class SkydioCloud:
    token: str = ""
    token_id: str = ""
    base: str = "https://api.skydio.com"

    @classmethod
    def from_env(cls) -> "SkydioCloud":
        token = os.environ.get("SKYDIO_API_TOKEN", "")
        if not token:
            raise RuntimeError(
                "SKYDIO_API_TOKEN not set. Copy .env.example to .env, fill in your "
                "enterprise token, and `source` it (or use python-dotenv)."
            )
        return cls(
            token=token,
            token_id=os.environ.get("SKYDIO_API_TOKEN_ID", ""),
            base=os.environ.get("SKYDIO_API_BASE", "https://api.skydio.com"),
        )

    @property
    def _headers(self) -> dict:
        # Skydio Cloud API authenticates with a JWT/API token bearer header.
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    def whoami(self) -> dict:
        """Validate the token (apidocs: WhoAmI). Good first call to confirm setup."""
        r = requests.get(f"{self.base}/api/v0/whoami", headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_flights(self, per_page: int = 50) -> list[dict]:
        """List recent flights. NOTE: confirm the exact path/params against
        https://apidocs.skydio.com for your API version."""
        r = requests.get(
            f"{self.base}/api/v0/flights",
            headers=self._headers,
            params={"per_page": per_page},
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
        return payload.get("data", {}).get("flights", payload.get("flights", []))

    def download_media(self, media_uuid: str, dest_dir: str | Path = "media") -> Path:
        """Download a captured media file by UUID for off-board barcode decoding."""
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        r = requests.get(
            f"{self.base}/api/v0/media_download/{media_uuid}",
            headers=self._headers,
            timeout=120,
            stream=True,
        )
        r.raise_for_status()
        out = dest / media_uuid
        with out.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
        return out


if __name__ == "__main__":
    # Smoke test: prints your org identity if a token is configured.
    client = SkydioCloud.from_env()
    print(client.whoami())
