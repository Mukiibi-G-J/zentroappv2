"""
Run tenant-scoped setup when optional modules are enabled (trial / admin override).

Must be called inside the tenant schema (e.g. from toggle_module API).
"""

from __future__ import annotations

import logging
from io import StringIO
from typing import Optional

from django.core.management import call_command

logger = logging.getLogger(__name__)

# module identifier -> management command name (tenant schema)
MODULE_SETUP_COMMANDS: dict[str, str] = {
    "restaurant": "seed_restaurant_module",
}


def run_module_setup(module_id: str, *, schema_name: Optional[str] = None) -> None:
    """
    Run idempotent setup for ``module_id`` in the current tenant schema.

    Raises on failure so callers can roll back module enablement.
    """
    command = MODULE_SETUP_COMMANDS.get(module_id)
    if not command:
        return

    label = schema_name or "current"
    logger.info("Running module setup %s for %s (schema=%s)", command, module_id, label)

    stdout = StringIO()
    stderr = StringIO()
    call_command(command, stdout=stdout, stderr=stderr, verbosity=0)

    out = stdout.getvalue().strip()
    if out:
        logger.debug("Module setup %s stdout: %s", command, out[:2000])
    err = stderr.getvalue().strip()
    if err:
        logger.warning("Module setup %s stderr: %s", command, err[:2000])
