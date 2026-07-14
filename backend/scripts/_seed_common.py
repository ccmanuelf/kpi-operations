"""
Shared base for the domain-split seeder modules: `ClientSpec` (the per-client
seeding parameters) and `rng_for` (deterministic per-key RNG). Imports NONE of
the other `_seed_*` modules — every other seed module imports from here.

No behavior change from the pre-split version — this is a pure move.
"""

import hashlib
import random
from dataclasses import dataclass

from backend.orm.client import ClientType


@dataclass(frozen=True)
class ClientSpec:
    client_id: str
    client_name: str
    client_type: ClientType
    num_employees: int
    num_work_orders: int


def rng_for(*key_parts: object) -> random.Random:
    """Deterministic RNG keyed on a stable sha256 of the parts (NOT builtin
    hash(), which is per-process salted for strings)."""
    key = "|".join(str(p) for p in key_parts).encode("utf-8")
    seed_int = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed_int)
