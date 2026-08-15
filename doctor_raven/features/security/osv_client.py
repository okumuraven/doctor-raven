"""Thin client for the OSV.dev vulnerability database API (no API key required)."""

import requests

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"


class OSVUnavailable(RuntimeError):
    pass


def query_single(ecosystem: str, name: str, version: str) -> list[dict]:
    payload = {"version": version, "package": {"name": name, "ecosystem": ecosystem}}
    try:
        resp = requests.post(OSV_QUERY_URL, json=payload, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OSVUnavailable(f"OSV.dev query failed: {exc}") from exc

    return resp.json().get("vulns", [])


def query_batch(packages: list[tuple[str, str, str]]) -> list[list[str]]:
    """packages: list of (ecosystem, name, version). Returns, per package, the list of matching vuln IDs."""
    if not packages:
        return []

    queries = [
        {"version": version, "package": {"name": name, "ecosystem": ecosystem}}
        for ecosystem, name, version in packages
    ]
    try:
        resp = requests.post(OSV_QUERYBATCH_URL, json={"queries": queries}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OSVUnavailable(f"OSV.dev batch query failed: {exc}") from exc

    results = resp.json().get("results", [])
    return [[vuln["id"] for vuln in result.get("vulns", [])] for result in results]
