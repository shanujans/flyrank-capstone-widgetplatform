"""
IP -> geo enrichment with a two-provider fallback chain.

Real mode: tries ip-api.com, falls back to ipapi.co, both free/no-key.
Mock mode (MOCK_GEO=true, the default — see .env.example): the two
MOCK_GEO_PROVIDER_*_DOWN flags let a test or a curl session deterministically
prove "A down -> B answers" and "both down -> submission still succeeds
without geo", without depending on real network calls or free-tier quotas.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("geo")


async def _call_provider_a(ip: str) -> tuple[str | None, str | None]:
    async with httpx.AsyncClient(timeout=settings.GEO_TIMEOUT_SECONDS) as client:
        resp = await client.get(settings.GEO_PROVIDER_A_URL.format(ip=ip))
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") == "fail":
            raise ValueError(f"provider A failed: {body.get('message')}")
        return body.get("country"), body.get("city")


async def _call_provider_b(ip: str) -> tuple[str | None, str | None]:
    async with httpx.AsyncClient(timeout=settings.GEO_TIMEOUT_SECONDS) as client:
        resp = await client.get(settings.GEO_PROVIDER_B_URL.format(ip=ip))
        resp.raise_for_status()
        body = resp.json()
        if body.get("error"):
            raise ValueError(f"provider B failed: {body.get('reason')}")
        return body.get("country_name"), body.get("city")


async def enrich_ip(ip: str) -> tuple[str | None, str | None, str | None]:
    """
    Returns (country, city, provider_used). provider_used is None when every
    provider failed — the caller stores the submission anyway (degrade,
    never fail).
    """
    if settings.MOCK_GEO:
        if not settings.MOCK_GEO_PROVIDER_A_DOWN:
            return "Sri Lanka", "Negombo", "provider_a"
        if not settings.MOCK_GEO_PROVIDER_B_DOWN:
            return "Sri Lanka", "Negombo", "provider_b"
        return None, None, None

    # Loopback/private addresses never resolve on real providers; treat them
    # like "no geo available" rather than spending a network round trip.
    if ip in ("unknown", "127.0.0.1", "testclient") or ip.startswith(("10.", "192.168.")):
        return None, None, None

    try:
        country, city = await _call_provider_a(ip)
        return country, city, "provider_a"
    except Exception as exc:  # noqa: BLE001 - any failure triggers fallback, by design
        logger.warning("geo provider A failed for %s: %s", ip, exc)

    try:
        country, city = await _call_provider_b(ip)
        return country, city, "provider_b"
    except Exception as exc:  # noqa: BLE001
        logger.warning("geo provider B failed for %s: %s", ip, exc)

    return None, None, None
