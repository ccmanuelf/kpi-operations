"""
Database Configuration API Endpoints

Provides admin endpoints for:
- Checking current database provider status
- Testing connections to target databases
- Initiating one-way database migration (SQLite → MariaDB/MySQL)
- Monitoring migration progress
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from backend.database import get_db, Base, engine as current_engine
from backend.db.factory import DatabaseProviderFactory
from backend.db.state import ProviderStateManager, MigrationState
from backend.db.migrations.schema_initializer import SchemaInitializer
from backend.db.migrations.demo_seeder import DemoDataSeeder
from backend.db.migrations.data_migrator import DataMigrator, DataMigrationError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from backend.auth.jwt import get_current_active_supervisor
from backend.schemas.user import User
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(
    prefix="/api/admin/database",
    tags=["database-config"],
    responses={404: {"description": "Not found"}},
)


# ============================================================================
# Request/Response Models
# ============================================================================


class DatabaseStatus(BaseModel):
    """Current database provider status."""

    current_provider: str
    migration_available: bool
    supported_targets: List[str]
    connection_info: Dict[str, Any] = Field(default_factory=dict)


class ConnectionTestRequest(BaseModel):
    """Request to test database connection."""

    target_url: str


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""

    success: bool
    provider: Optional[str] = None
    message: str
    connection_info: Dict[str, Any] = Field(default_factory=dict)


class MigrationRequest(BaseModel):
    """Request to start database migration."""

    target_provider: str = Field(..., description="Target provider: 'mariadb' or 'mysql'")
    target_url: str = Field(..., description="Database connection URL")
    confirmation_text: str = Field(..., description="Must be 'MIGRATE' to confirm")
    preserve_data: bool = Field(
        default=True, description="If True, copy existing data from source. If False, only seed demo data."
    )
    include_demo_data: bool = Field(
        default=True, description="If True, seed demo data after migration (recommended for new installs)."
    )


class MigrationStatusResponse(BaseModel):
    """Migration status response."""

    status: str
    current_step: Optional[str] = None
    tables_migrated: int = 0
    total_tables: int = 0
    current_table: Optional[str] = None
    rows_migrated: int = 0
    data_preserved: bool = False
    error_message: Optional[str] = None


class MigrationStartResponse(BaseModel):
    """Response after starting migration."""

    status: str
    message: str


class AvailableProvidersResponse(BaseModel):
    """Available database providers."""

    providers: Dict[str, Dict[str, Any]]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=DatabaseStatus)
async def get_database_status(
    current_user: User = Depends(get_current_active_supervisor),
):
    """Get current database provider status.

    Returns information about the current provider and whether
    migration to another provider is available.
    Requires supervisor or admin role.
    """
    state_manager = ProviderStateManager()
    factory = DatabaseProviderFactory.get_instance()

    current_provider = state_manager.get_current_provider()

    # Get connection info if engine exists
    connection_info = {}
    provider = factory.get_current_provider()
    if provider and factory._engine:
        connection_info = provider.get_connection_info(factory._engine)

    return DatabaseStatus(
        current_provider=current_provider,
        migration_available=current_provider == "sqlite",
        supported_targets=["mariadb", "mysql"],
        connection_info=connection_info,
    )


@router.get("/providers", response_model=AvailableProvidersResponse)
async def get_available_providers(
    current_user: User = Depends(get_current_active_supervisor),
):
    """Get information about available database providers.

    Requires supervisor or admin role.
    """
    factory = DatabaseProviderFactory.get_instance()
    return AvailableProvidersResponse(providers=factory.get_available_providers())


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(get_current_active_supervisor),
):
    """Test connection to target database.

    Attempts to connect to the specified database URL and validates
    the connection without affecting the current database.
    Requires supervisor or admin role.
    """
    factory = DatabaseProviderFactory.get_instance()

    try:
        result = factory.validate_connection(request.target_url)

        if result["success"]:
            return ConnectionTestResponse(
                success=True,
                provider=result["provider"],
                message="Connection successful",
                connection_info=result["connection_info"],
            )
        else:
            return ConnectionTestResponse(
                success=False,
                provider=result.get("provider"),
                message=result["message"],
                connection_info={},
            )

    except (SQLAlchemyError, ConnectionError, OSError) as e:
        logger.error("Connection test failed: %s", e)
        return ConnectionTestResponse(
            success=False,
            provider=None,
            message="Connection test failed. Check the target URL and ensure the database is reachable.",
            connection_info={},
        )


@router.post("/migrate", response_model=MigrationStartResponse)
async def start_migration(
    request: MigrationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_supervisor),
):
    """Start database migration (schema + demo data).

    This is a ONE-WAY operation from SQLite to MariaDB/MySQL.
    Requires explicit confirmation with 'MIGRATE' text.
    Requires supervisor or admin role.

    The migration runs in the background and progress can be
    monitored via the /migration/status endpoint.
    """
    # Validate confirmation
    if request.confirmation_text != "MIGRATE":
        raise HTTPException(
            status_code=400,
            detail="Invalid confirmation. Type 'MIGRATE' exactly to confirm this irreversible operation.",
        )

    # Check current provider
    state_manager = ProviderStateManager()
    current = state_manager.get_current_provider()

    if current != "sqlite":
        raise HTTPException(
            status_code=400, detail=f"Migration only available from SQLite. Current provider: {current}"
        )

    # Validate target provider
    if request.target_provider not in ("mariadb", "mysql"):
        raise HTTPException(
            status_code=400, detail=f"Invalid target provider: {request.target_provider}. Must be 'mariadb' or 'mysql'."
        )

    # Try to acquire migration lock
    if not state_manager.acquire_migration_lock():
        raise HTTPException(
            status_code=409, detail="Migration already in progress. Check /migration/status for details."
        )

    # Validate target connection
    factory = DatabaseProviderFactory.get_instance()
    try:
        result = factory.validate_connection(request.target_url)
        if not result["success"]:
            state_manager.release_migration_lock()
            raise HTTPException(status_code=400, detail=f"Cannot connect to target database: {result['message']}")
    except HTTPException:
        raise
    except (SQLAlchemyError, ConnectionError, OSError) as e:
        state_manager.release_migration_lock()
        logger.exception("Connection validation failed: %s", e)
        raise HTTPException(status_code=400, detail="Connection validation failed")

    # Start migration in background
    background_tasks.add_task(
        run_migration,
        state_manager,
        request.target_url,
        request.target_provider,
        request.preserve_data,
        request.include_demo_data,
    )

    migration_type = []
    if request.preserve_data:
        migration_type.append("data preservation")
    if request.include_demo_data:
        migration_type.append("demo data")

    logger.info(f"Migration started: SQLite → {request.target_provider} ({', '.join(migration_type)})")
    return MigrationStartResponse(
        status="started",
        message=f"Migration to {request.target_provider} started with {', '.join(migration_type)}. Monitor progress at /migration/status",
    )


@router.get("/migration/status", response_model=MigrationStatusResponse)
async def get_migration_status(
    current_user: User = Depends(get_current_active_supervisor),
):
    """Get current migration progress.

    Poll this endpoint to monitor migration progress.
    Requires supervisor or admin role.
    """
    state_manager = ProviderStateManager()
    state = state_manager.get_migration_state()

    if not state:
        return MigrationStatusResponse(status="idle")

    return MigrationStatusResponse(
        status=state.status,
        current_step=state.current_step,
        tables_migrated=state.tables_migrated,
        total_tables=state.total_tables,
        current_table=state.current_table,
        error_message=state.error_message,
    )


@router.get("/full-status")
async def get_full_status(
    current_user: User = Depends(get_current_active_supervisor),
):
    """Get complete database status including migration history.

    Requires supervisor or admin role.
    """
    state_manager = ProviderStateManager()
    return state_manager.get_full_status()


# ============================================================================
# Background Migration Task
# ============================================================================


async def run_migration(
    state_manager: ProviderStateManager,
    target_url: str,
    target_provider: str,
    preserve_data: bool = True,
    include_demo_data: bool = True,
):
    """Background migration: create schema, optionally copy data, optionally seed demo data.

    Args:
        state_manager: State manager for tracking progress.
        target_url: Database URL for target.
        target_provider: Target provider name.
        preserve_data: If True, copy existing data from source database.
        include_demo_data: If True, seed demo data after migration.
    """
    factory = DatabaseProviderFactory.get_instance()
    total_rows_migrated = 0

    try:
        # Initialize migration state
        state_manager.update_migration_state(
            MigrationState(
                status="in_progress",
                source_provider="sqlite",
                target_provider=target_provider,
                current_step="Connecting to target database...",
            )
        )

        # Create target engine
        provider = factory.create_provider(target_url)
        target_engine = provider.create_engine(target_url)

        # Step 1: Create schema
        state_manager.update_migration_state(
            MigrationState(
                status="in_progress",
                source_provider="sqlite",
                target_provider=target_provider,
                current_step="Creating database schema...",
            )
        )

        initializer = SchemaInitializer(target_engine, target_provider)

        def schema_progress(table_name: str, current: int, total: int):
            state_manager.update_migration_state(
                MigrationState(
                    status="in_progress",
                    source_provider="sqlite",
                    target_provider=target_provider,
                    current_step="Creating tables...",
                    current_table=table_name,
                    tables_migrated=current,
                    total_tables=total,
                )
            )

        created_tables = initializer.create_all_tables(Base.metadata, schema_progress)
        logger.info(f"Created {len(created_tables)} tables")

        # Step 2: Copy existing data (if preserve_data is True)
        if preserve_data:
            state_manager.update_migration_state(
                MigrationState(
                    status="in_progress",
                    source_provider="sqlite",
                    target_provider=target_provider,
                    current_step="Copying existing data from source database...",
                    tables_migrated=len(created_tables),
                    total_tables=len(created_tables),
                )
            )

            # Get source engine (current SQLite database)
            source_engine = current_engine

            # Create data migrator
            data_migrator = DataMigrator(
                source_engine=source_engine,
                target_engine=target_engine,
                source_provider="sqlite",
                target_provider=target_provider,
            )

            def data_progress(table_name: str, current: int, total: int, rows: int):
                nonlocal total_rows_migrated
                total_rows_migrated = rows
                state_manager.update_migration_state(
                    MigrationState(
                        status="in_progress",
                        source_provider="sqlite",
                        target_provider=target_provider,
                        current_step=f"Copying data: {table_name}...",
                        current_table=table_name,
                        tables_migrated=current,
                        total_tables=total,
                    )
                )

            migration_result = data_migrator.migrate_all_data(progress_callback=data_progress, skip_empty_tables=True)

            total_rows_migrated = migration_result.get("total_rows", 0)
            logger.info(f"Copied {total_rows_migrated} rows from source database")

            # Verify data migration
            verification = data_migrator.verify_migration()
            if not verification["verified"]:
                logger.warning(f"Data verification found mismatches: {verification['mismatches']}")

        # Step 3: Seed demo data (if include_demo_data is True)
        if include_demo_data:
            state_manager.update_migration_state(
                MigrationState(
                    status="in_progress",
                    source_provider="sqlite",
                    target_provider=target_provider,
                    current_step="Seeding demo data...",
                    tables_migrated=len(created_tables),
                    total_tables=len(created_tables),
                )
            )

            SessionLocal = sessionmaker(bind=target_engine)
            with SessionLocal() as session:
                seeder = DemoDataSeeder(session)

                def seed_progress(entity_name: str):
                    state_manager.update_migration_state(
                        MigrationState(
                            status="in_progress",
                            source_provider="sqlite",
                            target_provider=target_provider,
                            current_step=f"Seeding {entity_name}...",
                            tables_migrated=len(created_tables),
                            total_tables=len(created_tables),
                        )
                    )

                seeder.seed_all(seed_progress)
                logger.info(f"Demo data seeded: {seeder.get_seeded_counts()}")

        # Step 4: Update provider configuration
        state_manager.set_current_provider(target_provider)
        state_manager.set_database_url(target_url)

        # Record success
        state_manager.add_migration_history(source="sqlite", target=target_provider, success=True)

        completion_msg = "Migration complete!"
        if preserve_data:
            completion_msg += f" ({total_rows_migrated} rows preserved)"
        if include_demo_data:
            completion_msg += " (demo data seeded)"

        state_manager.update_migration_state(
            MigrationState(
                status="completed",
                source_provider="sqlite",
                target_provider=target_provider,
                current_step=completion_msg,
                tables_migrated=len(created_tables),
                total_tables=len(created_tables),
            )
        )

        logger.info(f"Migration completed successfully: sqlite → {target_provider}")

    except DataMigrationError as e:
        logger.exception("Data migration failed")

        state_manager.add_migration_history(
            source="sqlite", target=target_provider, success=False, error="DataMigrationError"
        )

        state_manager.update_migration_state(
            MigrationState(
                status="failed",
                source_provider="sqlite",
                target_provider=target_provider,
                current_step="Data migration failed",
                error_message="Data migration failed. Check server logs for details.",
            )
        )

    except (SQLAlchemyError, ConnectionError, OSError, RuntimeError) as e:
        logger.error("Migration failed with %s: %s", type(e).__name__, e)

        state_manager.add_migration_history(
            source="sqlite", target=target_provider, success=False, error=type(e).__name__
        )

        state_manager.update_migration_state(
            MigrationState(
                status="failed",
                source_provider="sqlite",
                target_provider=target_provider,
                current_step="Migration failed",
                error_message=f"Migration failed: {type(e).__name__}",
            )
        )

    except Exception as e:
        # Catch-all for background task — must not crash silently
        logger.exception("Migration failed with unexpected error: %s", type(e).__name__)

        state_manager.add_migration_history(
            source="sqlite", target=target_provider, success=False, error=type(e).__name__
        )

        state_manager.update_migration_state(
            MigrationState(
                status="failed",
                source_provider="sqlite",
                target_provider=target_provider,
                current_step="Migration failed",
                error_message="An unexpected error occurred during migration",
            )
        )

    finally:
        state_manager.release_migration_lock()
