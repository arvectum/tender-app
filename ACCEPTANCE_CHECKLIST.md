# ACCEPTANCE_CHECKLIST.md

## Install
- [ ] install.sh exists
- [ ] .env.example exists
- [ ] venv setup documented
- [ ] database initialization works
- [ ] dashboard starts
- [ ] scheduler starts

## Demo mode
- [ ] APP_MODE=demo works
- [ ] seed-demo works
- [ ] demo mode does not call real external sites
- [ ] smoke-test works
- [ ] dashboard shows demo data

## Production readiness
- [ ] auth enabled by default in production
- [ ] default secret key rejected in production
- [ ] doctor checks NO_PROXY
- [ ] healthcheck works
- [ ] backup works
- [ ] logs are written

## Business workflow
- [ ] parse command exists
- [ ] price search command exists
- [ ] calculate works
- [ ] evaluate works
- [ ] Excel export works
- [ ] watchlist works
- [ ] dashboard shows decision/risk/next_action

## Security
- [ ] secrets are redacted
- [ ] viewer cannot mutate data
- [ ] operator cannot manage users
- [ ] admin can manage users
- [ ] backup/restore admin-only

## Documentation
- [ ] README.md
- [ ] docs/INSTALL_MACOS.md
- [ ] docs/OPERATOR_GUIDE.md
- [ ] docs/ADMIN_GUIDE.md
- [ ] docs/TROUBLESHOOTING.md
- [ ] docs/DEMO_MODE.md
- [ ] docs/BACKUP_RESTORE.md
- [ ] docs/SECURITY.md
- [ ] docs/ROADMAP.md
