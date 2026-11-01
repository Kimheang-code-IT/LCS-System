# Create the S01 per-action synthetic e2e account on the local dev compose DB
# through the backend's own authorization service (set_role_permissions /
# set_user_roles), never raw casbin rows. The DB URL is read from a temp file
# and never printed. Disposable local dev database; synthetic account only.
$url = (Get-Content 'D:\freelancer\Freight Forwarding\.s01-db-url.txt' -Raw).Trim()
$env:DATABASE_URL = $url
Set-Location 'D:\freelancer\Freight Forwarding\backend'
uv run python -c "
import asyncio
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core import authorization
from app.core.security import hash_password
from app.modules.auth.models import User, UserCredential

CODES = [
    'master.transport_assets.view',
    'master.transport_assets.create',
    'master.party_roles.view',
    'master.party_roles.update',
    'master.party_roles.delete',
]

async def main():
    async with SessionLocal() as session:
        from app.modules.auth.models import Role
        role_row = (await session.execute(select(Role).where(Role.code == 'S01_E2E_ACTIONS'))).scalar_one_or_none()
        if role_row is None:
            role_row = Role(code='S01_E2E_ACTIONS', name='S01 E2E Per-Action', status='ACTIVE')
            session.add(role_row)
            await session.flush()
        await authorization.set_role_permissions(session, 'S01_E2E_ACTIONS', CODES)
        user = (await session.execute(select(User).where(User.username == 's01.e2e.actions'))).scalar_one_or_none()
        if user is None:
            u = User(user_code='S01_E2E_ACTIONS_U', username='s01.e2e.actions', system_identity='S01_E2E_ACTIONS', email='s01e2eactions@example.com', display_name='S01 E2E Per-Action', status='ACTIVE')
            session.add(u)
            await session.flush()
            session.add(UserCredential(user_id=u.id, password_hash=hash_password('Passw0rd!')))
        await authorization.set_user_roles(session, user.id if user else u.id, ['S01_E2E_ACTIONS'])
        await session.commit()
    print('per-action e2e user ready')

asyncio.run(main())
" 2>&1 | Select-Object -Last 4