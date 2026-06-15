"""create knowledge graph tables

Revision ID: e6a1b2c3d4f5
Revises: d4e5f6a7b8c9
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e6a1b2c3d4f5"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create target-level knowledge graph and mastery tables."""
    bind = op.get_bind()
    inspector = inspect(bind)

    knowledge_point_source = postgresql.ENUM(
        "ai_generated",
        "manual",
        "material_extracted",
        name="knowledge_point_source",
        create_type=False,
    )
    mastery_status = postgresql.ENUM(
        "unlearned",
        "weak",
        "basic",
        "proficient",
        name="knowledge_mastery_status",
        create_type=False,
    )
    knowledge_point_source.create(bind, checkfirst=True)
    mastery_status.create(bind, checkfirst=True)

    if not inspector.has_table("knowledge_points"):
        op.create_table(
            "knowledge_points",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("importance_weight", sa.Float(), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("source", knowledge_point_source, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["parent_id"], ["knowledge_points.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_id"], ["study_targets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_knowledge_points_id"), "knowledge_points", ["id"], unique=False)
        op.create_index(op.f("ix_knowledge_points_parent_id"), "knowledge_points", ["parent_id"], unique=False)
        op.create_index(op.f("ix_knowledge_points_target_id"), "knowledge_points", ["target_id"], unique=False)
        op.create_index(op.f("ix_knowledge_points_user_id"), "knowledge_points", ["user_id"], unique=False)

    if not inspector.has_table("material_knowledge_points"):
        op.create_table(
            "material_knowledge_points",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
            sa.Column("relevance_score", sa.Float(), nullable=False),
            sa.Column("evidence_text", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_material_knowledge_points_id"), "material_knowledge_points", ["id"], unique=False)
        op.create_index(op.f("ix_material_knowledge_points_knowledge_point_id"), "material_knowledge_points", ["knowledge_point_id"], unique=False)
        op.create_index(op.f("ix_material_knowledge_points_material_id"), "material_knowledge_points", ["material_id"], unique=False)

    if not inspector.has_table("user_knowledge_mastery"):
        op.create_table(
            "user_knowledge_mastery",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
            sa.Column("mastery_status", mastery_status, nullable=False),
            sa.Column("mastery_score", sa.Float(), nullable=False),
            sa.Column("accuracy", sa.Float(), nullable=False),
            sa.Column("answered_count", sa.Integer(), nullable=False),
            sa.Column("wrong_count", sa.Integer(), nullable=False),
            sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_id"], ["study_targets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "target_id",
                "knowledge_point_id",
                name="uq_user_knowledge_mastery_user_target_point",
            ),
        )
        op.create_index(op.f("ix_user_knowledge_mastery_id"), "user_knowledge_mastery", ["id"], unique=False)
        op.create_index(op.f("ix_user_knowledge_mastery_knowledge_point_id"), "user_knowledge_mastery", ["knowledge_point_id"], unique=False)
        op.create_index(op.f("ix_user_knowledge_mastery_mastery_status"), "user_knowledge_mastery", ["mastery_status"], unique=False)
        op.create_index(op.f("ix_user_knowledge_mastery_target_id"), "user_knowledge_mastery", ["target_id"], unique=False)
        op.create_index(op.f("ix_user_knowledge_mastery_user_id"), "user_knowledge_mastery", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop target-level knowledge graph and mastery tables."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("user_knowledge_mastery"):
        op.drop_index(op.f("ix_user_knowledge_mastery_user_id"), table_name="user_knowledge_mastery")
        op.drop_index(op.f("ix_user_knowledge_mastery_target_id"), table_name="user_knowledge_mastery")
        op.drop_index(op.f("ix_user_knowledge_mastery_mastery_status"), table_name="user_knowledge_mastery")
        op.drop_index(op.f("ix_user_knowledge_mastery_knowledge_point_id"), table_name="user_knowledge_mastery")
        op.drop_index(op.f("ix_user_knowledge_mastery_id"), table_name="user_knowledge_mastery")
        op.drop_table("user_knowledge_mastery")

    if inspector.has_table("material_knowledge_points"):
        op.drop_index(op.f("ix_material_knowledge_points_material_id"), table_name="material_knowledge_points")
        op.drop_index(op.f("ix_material_knowledge_points_knowledge_point_id"), table_name="material_knowledge_points")
        op.drop_index(op.f("ix_material_knowledge_points_id"), table_name="material_knowledge_points")
        op.drop_table("material_knowledge_points")

    if inspector.has_table("knowledge_points"):
        op.drop_index(op.f("ix_knowledge_points_user_id"), table_name="knowledge_points")
        op.drop_index(op.f("ix_knowledge_points_target_id"), table_name="knowledge_points")
        op.drop_index(op.f("ix_knowledge_points_parent_id"), table_name="knowledge_points")
        op.drop_index(op.f("ix_knowledge_points_id"), table_name="knowledge_points")
        op.drop_table("knowledge_points")

    postgresql.ENUM(
        "unlearned",
        "weak",
        "basic",
        "proficient",
        name="knowledge_mastery_status",
        create_type=False,
    ).drop(bind, checkfirst=True)
    postgresql.ENUM(
        "ai_generated",
        "manual",
        "material_extracted",
        name="knowledge_point_source",
        create_type=False,
    ).drop(bind, checkfirst=True)
