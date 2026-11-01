# Create synthetic S01 e2e users on the local dev compose database through the
# backend's own authorization service (set_user_roles), never raw casbin rows.
# The DB URL is read from a temp file and never printed.
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

async def main():
    async with SessionLocal() as session:
        for username, ident, role, display in [
            ('s01.e2e.full', 'S01_E2E_FULL', 'MANAGER', 'S01 E2E Full'),
            ('s01.e2e.viewer', 'S01_E2E_VIEWER', 'VIEWER', 'S01 E2E Viewer'),
        ]:
            existing = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
            if existing is None:
                u = User(user_code=username.upper(), username=username, system_identity=ident, email=username.replace('.', '') + '@example.com', display_name=display, status='ACTIVE')
                session.add(u)
                await session.flush()
                session.add(UserCredential(user_id=u.id, password_hash=hash_password('Passw0rd!')))
                await authorization.set_user_roles(session, u.id, [role])
        await session.commit()
    print('e2e users ready')

asyncio.run(main())
" 2>&1 | Select-Object -Last 4