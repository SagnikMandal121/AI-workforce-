from __future__ import annotations

import structlog


logger = structlog.get_logger(__name__)


class NotificationService:
    def send_email_verification(self, email: str, token: str) -> None:
        logger.info("email_verification_queued", email=email, token_preview=token[:16])

    def send_password_reset(self, email: str, token: str) -> None:
        logger.info("password_reset_queued", email=email, token_preview=token[:16])

    def send_invitation(self, email: str, token: str, role: str) -> None:
        logger.info("invite_queued", email=email, token_preview=token[:16], role=role)
