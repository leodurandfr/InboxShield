"""API routes for IMAP account management."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.account import Account, AccountSettings
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    CategoryActionsUpdate,
    FolderMappingUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services import imap_service
from app.services.encryption import encrypt
from app.services.scheduler import poll_account_by_id

router = APIRouter()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """List all IMAP accounts."""
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(data: AccountCreate, db: AsyncSession = Depends(get_db)):
    """Add a new IMAP account."""
    # Check duplicate email
    existing = await db.execute(select(Account).where(Account.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Un compte avec cet email existe déjà")

    # Auto-detect provider
    provider_info = imap_service.detect_provider(data.email)
    imap_host = data.imap_host or (provider_info.host if provider_info else None)
    imap_port = data.imap_port or (provider_info.port if provider_info else 993)
    smtp_host = data.smtp_host or (provider_info.smtp_host if provider_info else None)
    smtp_port = data.smtp_port or (provider_info.smtp_port if provider_info else 587)

    if not imap_host:
        raise HTTPException(
            status_code=400,
            detail="Impossible de détecter le serveur IMAP. Veuillez fournir imap_host.",
        )

    # Test connection before saving (run in thread to avoid blocking event loop)
    test_result = await asyncio.to_thread(
        imap_service.test_connection,
        host=imap_host,
        port=imap_port,
        username=data.email,
        password=data.password,
        email_address=data.email,
    )
    if not test_result.success:
        raise HTTPException(status_code=400, detail=test_result.error or "Connexion IMAP échouée")

    account = Account(
        name=data.name,
        email=data.email,
        provider=provider_info.provider if provider_info else None,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=data.email,
        encrypted_password=encrypt(data.password),
        folder_mapping=test_result.suggested_mapping,
    )
    db.add(account)
    await db.flush()  # Flush to get account.id

    # Create default account settings
    acct_settings = AccountSettings(account_id=account.id)
    db.add(acct_settings)

    return account


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get account details."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID, data: AccountUpdate, db: AsyncSession = Depends(get_db)
):
    """Update an IMAP account."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    update_data = data.model_dump(exclude_unset=True)

    # Handle password change
    if "password" in update_data:
        password = update_data.pop("password")
        if password:
            account.encrypted_password = encrypt(password)

    for key, value in update_data.items():
        setattr(account, key, value)

    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an IMAP account and all associated data."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    await db.delete(account)


# ---------------------------------------------------------------------------
# Connection & Folders
# ---------------------------------------------------------------------------


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(data: TestConnectionRequest):
    """Test IMAP connection without saving."""
    provider_info = imap_service.detect_provider(data.email)
    host = data.imap_host or (provider_info.host if provider_info else None)
    port = data.imap_port or (provider_info.port if provider_info else 993)

    if not host:
        return TestConnectionResponse(
            success=False,
            error="UNKNOWN_PROVIDER",
            message="Impossible de détecter le serveur IMAP. Veuillez fournir imap_host.",
        )

    result = await asyncio.to_thread(
        imap_service.test_connection,
        host=host,
        port=port,
        username=data.email,
        password=data.password,
        email_address=data.email,
    )

    return TestConnectionResponse(
        success=result.success,
        provider=result.provider,
        folders=result.folders if result.success else None,
        suggested_mapping=result.suggested_mapping if result.success else None,
        error=result.error_code if not result.success else None,
        message=result.error if not result.success else None,
    )


@router.post("/{account_id}/poll")
async def poll_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Force an immediate email poll for this account."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    poll_result = await poll_account_by_id(account_id)
    if "error" in poll_result:
        raise HTTPException(status_code=500, detail=poll_result["error"])
    return poll_result


@router.get("/{account_id}/folders")
async def list_folders(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List IMAP folders for an account."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    from app.services.encryption import decrypt

    password = decrypt(account.encrypted_password)

    try:
        folder_mapping = imap_service.discover_folders(
            host=account.imap_host,
            port=account.imap_port,
            username=account.username,
            password=password,
        )
        return {
            "folders": folder_mapping.folders,
            "suggested_mapping": folder_mapping.suggested_mapping,
            "current_mapping": account.folder_mapping,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erreur IMAP: {e}")


@router.put("/{account_id}/folder-mapping", response_model=AccountResponse)
async def update_folder_mapping(
    account_id: uuid.UUID,
    data: FolderMappingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update IMAP folder mapping."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    account.folder_mapping = data.folder_mapping
    return account


@router.put("/{account_id}/category-actions")
async def update_category_actions(
    account_id: uuid.UUID,
    data: CategoryActionsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Configure default category → IMAP folder actions."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    # Get or create account settings
    settings_result = await db.execute(
        select(AccountSettings).where(AccountSettings.account_id == account_id)
    )
    acct_settings = settings_result.scalar_one_or_none()

    if not acct_settings:
        acct_settings = AccountSettings(
            account_id=account_id,
            default_category_action=data.default_category_action,
        )
        db.add(acct_settings)
    else:
        acct_settings.default_category_action = data.default_category_action

    return {"status": "ok", "default_category_action": data.default_category_action}
