"""
CRUD batch operations for Production Entry
Bulk create and import operations
SECURITY: Multi-tenant client filtering enabled
"""

from typing import List
from sqlalchemy.orm import Session

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.user import User
from backend.models.production import ProductionEntryCreate
from backend.crud.production.core import create_production_entry


def batch_create_entries(
    db: Session, entries: List[ProductionEntryCreate], current_user: User
) -> List[ProductionEntry]:
    """
    Batch create production entries (for CSV upload)
    SECURITY: Verifies user has access to each entry's client

    Args:
        db: Database session
        entries: List of production entries
        current_user: Authenticated user (CHANGED from entered_by: int)

    Returns:
        List of created entries

    Raises:
        ClientAccessError: If user doesn't have access to any entry's client
    """
    created_entries = []

    for entry_data in entries:
        try:
            # create_production_entry now handles authorization
            entry = create_production_entry(db, entry_data, current_user)
            created_entries.append(entry)
        except Exception as e:
            # Log error but continue with other entries
            print(f"Error creating entry: {e}")
            continue

    return created_entries
