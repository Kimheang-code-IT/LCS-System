# Recreate the S01 narrow-page synthetic e2e account on the local dev compose
# DB through the backend's own authorization service (set_role_permissions /
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
    'dashboard.view', 'admin.audit_logs.view', 'admin.archive.view',
    'configuration.view', 'settings.app_config.view',
    'master.business_parties.view', 'master.container_types.view',
    'master.currencies.view', 'master.fee_types.view', 'master.party_roles.view',
    'master.place_roles.view', 'master.reference.view',
    'master.trade_directions.view', 'master.transport_assets.view', 'master.transport_types.view',
]

async def main():
    async with SessionLocal() as session:
        from app.modules.auth.models import Role
        user = (await session.execute(select(User).where(User.username == 's01.e2e.pages'))).scalar_one_or_none()
        if user is None:
            u = User(user_code='S01_E2E_PAGES', username='s01.e2e.pages', system_identity='S01_E2E_PAGES', email='s01e2epages@example.com', display_name='S01 E2E Pages', status='ACTIVE')
            session.add(u)
            await session.flush()
            session.add(UserCredential(user_id=u.id, password_hash=hash_password('Passw0rd!')))
        else:
            u = user
        await authorization.set_role_permissions(session, 'S01_E2E_PAGES', CODES)
        await authorization.set_user_roles(session, u.id, ['S01_E2E_PAGES'])
        await session.commit()
    print('narrow e2e user ready')

asyncio.run(main())
" 2>&1 | Select-Object -Last 3