"""create projects and tasks

Revision ID: d1f95be0a028
Revises:
Create Date: 2026-10-28 15:39:35.255901

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f95be0a028"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(
        "ux_projects_name_lower",
        "projects",
        [sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name=op.f("ck_tasks_priority")
        ),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')", name=op.f("ck_tasks_status")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_tasks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(
        "ix_tasks_project_id_created_at",
        "tasks",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ux_tasks_project_id_title_lower",
        "tasks",
        ["project_id", sa.literal_column("lower(title)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_tasks_project_id_title_lower", table_name="tasks")
    op.drop_index("ix_tasks_project_id_created_at", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ux_projects_name_lower", table_name="projects")
    op.drop_table("projects")
