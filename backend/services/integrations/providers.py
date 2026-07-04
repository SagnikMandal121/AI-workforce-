from __future__ import annotations

import hashlib
from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from backend.core.security import utcnow
from backend.database.models.integration import Integration, IntegrationProvider


@dataclass(frozen=True)
class ProviderConnectResult:
    authorization_url: str
    state: str


@dataclass(frozen=True)
class ProviderAuthResult:
    external_account_id: str
    display_name: str
    access_token: str
    refresh_token: str | None
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime | None
    scopes: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProviderValidationResult:
    valid: bool
    message: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProviderActionResult:
    success: bool
    message: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ProviderDisconnectResult:
    success: bool
    message: str


class IntegrationProviderBase(ABC):
    provider: IntegrationProvider
    display_name: str
    default_scopes: list[str]

    def connect(self, *, integration: Integration, state: str, scopes: list[str]) -> ProviderConnectResult:
        return ProviderConnectResult(
            authorization_url=f"https://auth.placeholder.local/{self.provider.value}/authorize",
            state=state,
        )

    def authenticate(
        self,
        *,
        integration: Integration,
        authorization_code: str,
        redirect_uri: str | None,
        scopes: list[str],
    ) -> ProviderAuthResult:
        token_seed = f"{self.provider.value}:{integration.organization_id}:{authorization_code}:{redirect_uri or ''}"
        digest = hashlib.sha256(token_seed.encode("utf-8")).hexdigest()
        now = utcnow()
        return ProviderAuthResult(
            external_account_id=digest[:24],
            display_name=integration.display_name,
            access_token=f"access_{digest}",
            refresh_token=f"refresh_{digest}",
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=30),
            scopes=scopes or list(self.default_scopes),
            metadata={"provider": self.provider.value, "mode": "placeholder"},
        )

    def refresh_token(
        self,
        *,
        integration: Integration,
        refresh_token: str,
        scopes: list[str],
    ) -> ProviderAuthResult:
        token_seed = f"refresh:{self.provider.value}:{integration.id}:{refresh_token}"
        digest = hashlib.sha256(token_seed.encode("utf-8")).hexdigest()
        now = utcnow()
        return ProviderAuthResult(
            external_account_id=integration.external_account_id or digest[:24],
            display_name=integration.display_name,
            access_token=f"refreshed_access_{digest}",
            refresh_token=f"refreshed_refresh_{digest}",
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=30),
            scopes=scopes or list(self.default_scopes),
            metadata={"provider": self.provider.value, "mode": "refresh"},
        )

    def validate(self, *, integration: Integration) -> ProviderValidationResult:
        return ProviderValidationResult(
            valid=True,
            message=f"{self.display_name} connection is healthy",
            metadata={"provider": self.provider.value, "checked_at": utcnow().isoformat()},
        )

    def execute_action(
        self,
        *,
        integration: Integration,
        action: str,
        payload: dict[str, Any],
    ) -> ProviderActionResult:
        return ProviderActionResult(
            success=True,
            message=f"Placeholder execution for {self.provider.value}:{action}",
            payload={
                "provider": self.provider.value,
                "integration_id": str(integration.id),
                "action": action,
                "payload": payload,
            },
        )

    def disconnect(self, *, integration: Integration) -> ProviderDisconnectResult:
        return ProviderDisconnectResult(success=True, message=f"{self.display_name} disconnected")


class GmailIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.GMAIL
    display_name = "Gmail"
    default_scopes = ["gmail.read", "gmail.send", "calendar.read"]


class OutlookIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.OUTLOOK
    display_name = "Outlook"
    default_scopes = ["mail.read", "mail.send", "calendar.read"]


class GoogleCalendarIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.GOOGLE_CALENDAR
    display_name = "Google Calendar"
    default_scopes = ["calendar.read", "calendar.write"]


class WhatsAppBusinessIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.WHATSAPP_BUSINESS
    display_name = "WhatsApp Business"
    default_scopes = ["messages.read", "messages.write"]


class TwilioIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.TWILIO
    display_name = "Twilio"
    default_scopes = ["sms.read", "sms.send", "voice.send"]


class SlackIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.SLACK
    display_name = "Slack"
    default_scopes = ["channels.read", "messages.read", "messages.write"]


class HubSpotIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.HUBSPOT
    display_name = "HubSpot"
    default_scopes = ["crm.objects.read", "crm.objects.write"]


class SalesforceIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.SALESFORCE
    display_name = "Salesforce"
    default_scopes = ["salesforce.read", "salesforce.write"]


class GoogleDriveIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.GOOGLE_DRIVE
    display_name = "Google Drive"
    default_scopes = ["drive.read", "drive.write"]


class NotionIntegrationProvider(IntegrationProviderBase):
    provider = IntegrationProvider.NOTION
    display_name = "Notion"
    default_scopes = ["notion.read", "notion.write"]


class IntegrationRegistry:
    def __init__(self) -> None:
        providers = [
            GmailIntegrationProvider(),
            OutlookIntegrationProvider(),
            GoogleCalendarIntegrationProvider(),
            WhatsAppBusinessIntegrationProvider(),
            TwilioIntegrationProvider(),
            SlackIntegrationProvider(),
            HubSpotIntegrationProvider(),
            SalesforceIntegrationProvider(),
            GoogleDriveIntegrationProvider(),
            NotionIntegrationProvider(),
        ]
        self._providers = {provider.provider: provider for provider in providers}

    def get(self, provider: IntegrationProvider) -> IntegrationProviderBase:
        return self._providers[provider]

    def list_supported(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": provider.value,
                "display_name": integration.display_name,
                "lifecycle": [
                    "connect",
                    "authenticate",
                    "refresh_token",
                    "validate",
                    "execute_action",
                    "disconnect",
                ],
                "default_scopes": list(integration.default_scopes),
            }
            for provider, integration in sorted(self._providers.items(), key=lambda item: item[0].value)
        ]