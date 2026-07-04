# Deployment guide

## Free hosted topology

- Frontend: Vercel Hobby, root directory `frontend`
- API: Render free web service using `backend/Dockerfile`
- Database: Neon or Supabase free PostgreSQL with the `vector` extension
- Redis: local Redis for development; an available free Redis-compatible provider for demos
- Storage: MinIO locally; deploy MinIO only where persistent disk is available
- Model: Ollama on the presenter/developer machine. Hosted free instances generally lack the RAM and persistence needed for reliable LLM inference.

Set every variable from `.env.example` in the deployment dashboard. Change `NEXT_PUBLIC_API_URL` to the public Render API URL and `CORS_ORIGINS` to the Vercel origin. Use provider callback URLs ending in `/api/v1/auth/{provider}/callback`.

## Release checklist

1. Generate a 32+ byte JWT secret and rotate demo credentials.
2. Apply Alembic migrations before new API instances receive traffic.
3. Require HTTPS and secure, HTTP-only, SameSite cookies for refresh tokens.
4. Restrict database, MinIO, and Redis to private networking.
5. Configure SMTP SPF, DKIM, and DMARC.
6. Run `npm run build`, `ruff check .`, and `pytest` in CI.
7. Verify login, check-in/out, leave approval, payroll explanation, document search, and audit export.

