// Create S01 synthetic e2e users on the local dev compose DB through the
// backend's own authorization service (no raw casbin writes). Secrets are read
// from infrastructure/.env and never printed.
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const env = Object.fromEntries(
  readFileSync('infrastructure/.env', 'utf8').split(/\r?\n/).filter((l) => /^[A-Z_]+=.+/.test(l)).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)])
);
const db = env.POSTGRES_DB;
const user = env.POSTGRES_USER;
const pass = env.POSTGRES_PASSWORD;
writeFileSync('D:/freelancer/Freight Forwarding/.s01-db-url.txt', `postgresql+asyncpg://${user}:${pass}@127.0.0.1:5432/${db}\n`);
console.log('target database:', db, '(local ff-db compose container)');