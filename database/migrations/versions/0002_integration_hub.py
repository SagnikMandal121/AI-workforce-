"""Integration hub schema.

Revision ID: 0002_integration_hub
Revises: 0001_initial
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_integration_hub"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "provider", name="uq_integrations_org_provider"),
    )
    op.create_index("ix_integrations_organization_status", "integrations", ["organization_id", "status"])

    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "integration_id",
            sa.Uuid(),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("access_token_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=4096), nullable=True),
        sa.Column("token_type", sa.String(length=64), nullable=False, server_default=sa.text("'oauth2'")),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_error", sa.String(length=1024), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_oauth_tokens_expires_at", "oauth_tokens", ["access_token_expires_at"])

    op.create_table(
        "integration_logs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "integration_id",
            sa.Uuid(),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'ok'")),
        sa.Column("message", sa.String(length=1024), nullable=False, server_default=sa.text("''")),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_integration_logs_integration_action", "integration_logs", ["integration_id", "action"])

    op.create_table(
        "integration_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "integration_id",
            sa.Uuid(),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("can_access", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("can_configure", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "granted_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("integration_id", "user_id", name="uq_integration_permissions_user"),
    )
    op.create_index("ix_integration_permissions_user", "integration_permissions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_permissions_user", table_name="integration_permissions")
    op.drop_table("integration_permissions")
    op.drop_index("ix_integration_logs_integration_action", table_name="integration_logs")
    op.drop_table("integration_logs")
    op.drop_index("ix_oauth_tokens_expires_at", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
    op.drop_index("ix_integrations_organization_status", table_name="integrations")
    op.drop_table("integrations")