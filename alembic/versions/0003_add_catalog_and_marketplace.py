"""add catalog and marketplace tables

Revision ID: 0003_add_catalog_and_marketplace
Revises: 0002
Create Date: 2026-04-20

"""

import sqlalchemy as sa
from alembic import op

revision = "0003_add_catalog_and_marketplace"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(50), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "telegram_notifications", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("yookassa_payment_id", sa.String(255), nullable=True),
        sa.Column("yookassa_subscription_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index(
        "ix_subscriptions_yookassa_payment_id",
        "subscriptions",
        ["yookassa_payment_id"],
    )

    # marketplace_credentials
    op.create_table(
        "marketplace_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("marketplace", sa.String(20), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("encrypted_client_id", sa.Text(), nullable=True),
        sa.Column(
            "is_valid", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "publish_mode", sa.String(10), nullable=False, server_default="manual"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "marketplace", name="uq_user_marketplace"),
    )
    op.create_index(
        "ix_marketplace_credentials_user_id", "marketplace_credentials", ["user_id"]
    )

    # catalog_batches
    op.create_table(
        "catalog_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uid", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("templates.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("marketplace", sa.String(20), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column(
            "total_items", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "processed_items", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "failed_items", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "output_format", sa.String(10), nullable=False, server_default="png"
        ),
        sa.Column("column_mapping", sa.Text(), nullable=True),
        sa.Column("zip_path", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("publish_task_id", sa.String(255), nullable=True),
        sa.Column("publish_status", sa.String(20), nullable=True),
        sa.Column(
            "published_items", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "publish_failed_items", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("telegram_chat_id", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_catalog_batches_user_id", "catalog_batches", ["user_id"])
    op.create_index("ix_catalog_batches_status", "catalog_batches", ["status"])

    # catalog_items
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uid", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "catalog_batch_id",
            sa.Integer(),
            sa.ForeignKey("catalog_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column(
            "title", sa.String(500), nullable=False, server_default=""
        ),
        sa.Column("price", sa.String(50), nullable=True),
        sa.Column("old_price", sa.String(50), nullable=True),
        sa.Column("discount", sa.String(20), nullable=True),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("extra_fields", sa.Text(), nullable=True),
        sa.Column(
            "generation_id",
            sa.Integer(),
            sa.ForeignKey("generations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "generation_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_catalog_items_user_id", "catalog_items", ["user_id"])
    op.create_index(
        "ix_catalog_items_batch_id", "catalog_items", ["catalog_batch_id"]
    )
    op.create_index(
        "ix_catalog_items_status", "catalog_items", ["generation_status"]
    )


def downgrade() -> None:
    op.drop_table("catalog_items")
    op.drop_table("catalog_batches")
    op.drop_table("marketplace_credentials")
    op.drop_table("subscriptions")
    op.drop_column("users", "telegram_notifications")
    op.drop_column("users", "telegram_chat_id")
