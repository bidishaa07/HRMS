# Authentication setup

Aurora supports password registration/login, generated login IDs, short-lived JWT access cookies, rotated refresh cookies, logout revocation, role-based API authorization, and Google OAuth 2.0.

## Local environment

Copy `.env.example` to `.env` at the repository root. The API loads both the root `.env` and `backend/.env`; Docker Compose passes the root file directly.

Set a strong secret before using real employee data:

```env
JWT_SECRET=replace-with-at-least-32-random-bytes
FRONTEND_URL=http://localhost:3000
COOKIE_SECURE=false
```

Use `COOKIE_SECURE=true` behind HTTPS. Access and refresh tokens are stored in HTTP-only, SameSite cookies; API endpoints also accept a Bearer access token for external clients.

## Google OAuth 2.0

1. Create an OAuth 2.0 Web application in Google Cloud Console.
2. Add `http://localhost:8000/api/v1/auth/oauth/google/callback` as an authorized redirect URI.
3. Add the production API callback separately when deploying.
4. Configure:

```env
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/oauth/google/callback
```

The **Settings** page reports whether Google's client ID and secret were loaded. It never displays secret values.

## Demo administrator

- Email: `admin@aurorahr.example.com`
- Password: `Aurora@123`

Change or remove this seeded account before production. New-company registration makes the first member an administrator and generates a login ID in this format:

```text
<company initials><first 2 first name><first 2 last name><joining year><4-digit serial>
```

Example: `NWJADO20260001`.
