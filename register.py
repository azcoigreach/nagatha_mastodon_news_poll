"""Provider registration with Nagatha Core."""
import os
import asyncio
import logging
from typing import Dict, Any
import httpx

from config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("register")


async def wait_for_core(client: httpx.AsyncClient, timeout_s: int = 60):
    """Wait for Nagatha Core to become available."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await client.get(f"{settings.core_url}/ping")
            if r.status_code == 200:
                log.info("Nagatha Core is up: %s", r.json())
                return
        except Exception:
            pass
        log.info("Waiting for Nagatha Core...")
        await asyncio.sleep(2)
    raise RuntimeError("Nagatha Core did not become ready in time")


async def wait_for_provider(timeout_s: int = 60):
    """Wait for this provider's API to become available."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    # Use the provider_base_url directly (should work from within Docker network)
    provider_url = settings.provider_base_url
    log.info(f"Waiting for provider API at {provider_url}/health")
    
    while asyncio.get_event_loop().time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{provider_url}/health")
                if r.status_code == 200:
                    log.info("Provider API is up: %s", r.json())
                    return
        except Exception as e:
            log.debug(f"Provider health check failed: {e}")
            pass
        log.info("Waiting for provider API...")
        await asyncio.sleep(2)
    raise RuntimeError("Provider API did not become ready in time")


async def register_provider(client: httpx.AsyncClient, retries: int = 5, delay_s: int = 2) -> bool:
    """Register this provider with Nagatha Core."""
    payload: Dict[str, Any] = {
        "provider_id": settings.provider_id,
        "base_url": settings.provider_base_url,
    }
    
    for attempt in range(retries):
        try:
            r = await client.post(
                f"{settings.core_url}/providers/register",
                json=payload
            )
            if r.status_code in (200, 201):
                log.info("Registered provider: %s", r.json())
                return True
            log.warning("Registration attempt %d failed: %s", attempt + 1, r.text)
        except Exception as exc:
            log.warning("Registration error: %s", exc)
        await asyncio.sleep(delay_s)
    return False


async def heartbeat_loop(client: httpx.AsyncClient):
    """Send periodic heartbeat to Nagatha Core."""
    while True:
        try:
            r = await client.post(
                f"{settings.core_url}/providers/{settings.provider_id}/heartbeat"
            )
            if r.status_code == 200:
                log.info("Heartbeat ok")
            else:
                log.warning("Heartbeat status: %s", r.status_code)
        except Exception as exc:
            log.warning("Heartbeat error: %s", exc)
        await asyncio.sleep(30)


async def main():
    """Main registration and heartbeat loop."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        await wait_for_core(client)
        await wait_for_provider()
        
        ok = await register_provider(client)
        if not ok:
            log.error("Registration failed after retries; continuing heartbeat attempts.")
        
        await heartbeat_loop(client)


if __name__ == "__main__":
    asyncio.run(main())
