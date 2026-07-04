import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const session = request.cookies.get("aurora_access");
  const isAuthPage = request.nextUrl.pathname === "/login" || request.nextUrl.pathname === "/register";
  if (!session && !isAuthPage) return NextResponse.redirect(new URL("/login", request.url));
  if (session && isAuthPage) return NextResponse.redirect(new URL("/", request.url));
  return NextResponse.next();
}

export const config = { matcher: ["/", "/login", "/register"] };

