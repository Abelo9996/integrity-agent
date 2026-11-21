"""Polite bounded HTTP, content-addressed cache, explicit download policy."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import sqlite3
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx


class AccessError(RuntimeError):
    pass


class Transport:
    def __init__(self, root: Path, email: str, *, client=None, interval: float = 1.0):
        if "@" not in email or email.endswith("example.com"):
            raise ValueError("Set a real contact email in INTEGRITY_CONTACT_EMAIL.")
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / "http.sqlite3")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS response (key TEXT PRIMARY KEY, path TEXT, retrieved REAL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS request_slot "
            "(host TEXT PRIMARY KEY, next_start REAL, interval REAL)"
        )
        self.client = client or httpx.Client(
            timeout=60,
            follow_redirects=False,
            headers={"User-Agent": f"integrity-agent/0.1 (mailto:{email})"},
        )
        self.email = email
        self.interval = interval
        self.robots: dict[str, RobotFileParser] = {}

    def close(self):
        self.client.close()
        self.db.close()

    def _pace(self, host: str):
        """Reserve a host slot across processes sharing this cache directory."""
        interval = max(
            self.interval, 3.1 if "arxiv.org" in host else 10.1 if host == "api.wiley.com" else 0
        )
        now = time.time()
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT next_start, interval FROM request_slot WHERE host=?", (host,)
            ).fetchone()
            interval = max(interval, row[1]) if row else interval
            start = max(now, row[0] - row[1] + interval) if row else now
            self.db.execute(
                "INSERT OR REPLACE INTO request_slot VALUES (?, ?, ?)",
                (host, start + interval, interval),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        time.sleep(max(0, start - time.time()))

    @staticmethod
    def validate_url(url: str):
        u = urlsplit(url)
        if (
            u.scheme != "https"
            or not u.hostname
            or u.username
            or u.password
            or u.port not in (None, 443)
        ):
            raise AccessError("Only public HTTPS URLs without credentials are accepted.")
        try:
            addresses = socket.getaddrinfo(u.hostname, 443)
        except OSError as exc:
            raise AccessError("DNS lookup failed") from exc
        if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise AccessError("Private/reserved network destination rejected.")

    def _request(self, url: str, headers: dict, limit: int) -> bytes:
        host = urlsplit(url).hostname or ""
        for attempt in range(4):
            self._pace(host)
            with self.client.stream("GET", url, headers=headers) as response:
                if response.status_code in (429, 500, 502, 503, 504):
                    retry = response.headers.get("Retry-After", "")
                    delay = float(retry) if retry.isdigit() else 2 ** (attempt + 1)
                    if delay > 60:
                        raise AccessError("Server requested a long retry; retry the run later.")
                    time.sleep(delay)
                    continue
                if response.is_redirect:
                    raise AccessError("Unexpected redirect in low-level request.")
                if response.status_code != 200:
                    raise AccessError(f"HTTP {response.status_code} from {host}")
                buf = bytearray()
                for chunk in response.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > limit:
                        raise AccessError(f"Download exceeded {limit} bytes")
                return bytes(buf)
        raise AccessError("Retries exhausted")

    def _allowed(self, url: str):
        u = urlsplit(url)
        origin = f"{u.scheme}://{u.netloc}"
        if origin not in self.robots:
            self.validate_url(origin + "/robots.txt")
            # 404 means no robots policy. Other failures fail closed.
            try:
                content = self._request(origin + "/robots.txt", {}, 1_000_000).decode()
            except AccessError as exc:
                if "HTTP 404 " in str(exc):
                    content = ""
                else:
                    raise AccessError("Could not establish robots policy") from exc
            rp = RobotFileParser()
            rp.parse(content.splitlines())
            self.robots[origin] = rp
        rp = self.robots[origin]
        if not rp.can_fetch("integrity-agent", url):
            raise AccessError("robots.txt disallows retrieval")
        delay = rp.crawl_delay("integrity-agent") or rp.crawl_delay("*")
        if delay:
            self.interval = max(self.interval, delay)

    def get(
        self, url: str, *, params=None, headers=None, download=False, limit=100_000_000, ttl=86400
    ) -> bytes:
        request_url = str(httpx.URL(url, params=params)) if params else url
        # Auth-dependent responses are isolated without storing credentials.
        key = hashlib.sha256(
            (request_url + json.dumps(headers or {}, sort_keys=True)).encode()
        ).hexdigest()
        row = self.db.execute("SELECT path, retrieved FROM response WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[1] < ttl and (self.root / row[0]).exists():
            cached = (self.root / row[0]).read_bytes()
            if len(cached) <= limit and hashlib.sha256(cached).hexdigest() == Path(row[0]).stem:
                return cached
        current = request_url
        req_headers = headers or {}
        for _ in range(6):
            self.validate_url(current)
            if download:
                self._allowed(current)
            host = urlsplit(current).hostname or ""
            self._pace(host)
            # Probe with streamed GET, reuse body; do not issue HEAD (often unsupported).
            with self.client.stream("GET", current, headers=req_headers) as response:
                if response.is_redirect:
                    target = urljoin(current, response.headers["Location"])
                    if urlsplit(target).netloc != urlsplit(current).netloc:
                        req_headers = {}  # never forward API credentials to a different host
                    current = target
                    continue
                if response.status_code in (429, 500, 502, 503, 504):
                    retry = response.headers.get("Retry-After", "")
                    wait = float(retry) if retry.isdigit() else 2
                    if wait > 60:
                        raise AccessError("Server requested a long retry; retry later.")
                    time.sleep(wait)
                    content = self._request(current, req_headers, limit)
                else:
                    if response.status_code != 200:
                        raise AccessError(f"HTTP {response.status_code} from {host}")
                    buf = bytearray()
                    for chunk in response.iter_bytes():
                        buf.extend(chunk)
                        if len(buf) > limit:
                            raise AccessError("Download size limit exceeded")
                    content = bytes(buf)
            name = hashlib.sha256(content).hexdigest() + ".blob"
            (self.root / name).write_bytes(content)
            self.db.execute(
                "INSERT OR REPLACE INTO response VALUES (?, ?, ?)", (key, name, time.time())
            )
            self.db.commit()
            return content
        raise AccessError("Too many redirects")

    def json(self, url: str, **kwargs):
        return json.loads(self.get(url, **kwargs))
