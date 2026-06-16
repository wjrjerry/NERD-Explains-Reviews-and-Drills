from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository


class BootstrapService:
    """Application startup initialization helpers."""

    @staticmethod
    async def ensure_initial_admin() -> None:
        """Create the configured initial admin when that username is absent."""
        username = (settings.initial_admin_username or "").strip()
        password = settings.initial_admin_password or ""
        display_name = (settings.initial_admin_display_name or "").strip() or username

        if not username or not password:
            return

        async with AsyncSessionLocal() as db:
            existing_user = await UserRepository.get_by_username(db, username)
            if existing_user is not None:
                return

            try:
                await UserRepository.create_user(
                    db,
                    username=username,
                    hashed_password=get_password_hash(password),
                    display_name=display_name,
                    role=UserRole.admin,
                )
            except IntegrityError:
                await db.rollback()
            except SQLAlchemyError:
                await db.rollback()
