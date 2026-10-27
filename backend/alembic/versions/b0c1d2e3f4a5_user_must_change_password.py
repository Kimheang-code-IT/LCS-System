"""Force a password change after an administrator sets one.

An administrator can already choose a user's password when creating the account,
but there was no way to help a user who had forgotten theirs: ``change_password``
requires the current password and the self-service reset needs an email the user
can actually receive. This revision adds the state that makes an administrative
reset safe.

``user_credentials.must_change_password`` records that the current password was
chosen by somebody other than its owner. While it is set:

* the access token carries a ``pwd`` claim, so ``get_current_context`` can refuse
  every route except changing the password without an extra query per request;
* the change-password flow clears it, so the flag cannot outlive the reset it
  belongs to.

Defaulting to ``false`` leaves every existing credential untouched: nobody is
locked out of anything by this migration.

Additive only — no existing column is altered or dropped.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: str | None = "a9b0c1d2e3f4"
# See docs/11_deployment_and_security.md §8.
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_credentials",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_credentials", "must_change_password")