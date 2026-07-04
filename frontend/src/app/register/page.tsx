import { Suspense } from "react";
import { AuthShell } from "@/components/auth-shell";

export default function RegisterPage() { return <Suspense><AuthShell mode="register" /></Suspense>; }

