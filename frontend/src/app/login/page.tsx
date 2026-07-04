import { Suspense } from "react";
import { AuthShell } from "@/components/auth-shell";

export default function LoginPage() { return <Suspense><AuthShell mode="login" /></Suspense>; }

