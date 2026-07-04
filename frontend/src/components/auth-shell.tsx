"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, Eye, EyeOff, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";

export function AuthShell({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const search = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState<"admin" | "employee">("employee");
  const [error, setError] = useState(search.get("error") ? "Single sign-on could not be completed. Check the OAuth redirect configuration." : "");
  const [loginId, setLoginId] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (mode === "login") {
        await api.login({ login: String(form.get("login")), password: String(form.get("password")), role });
      } else {
        const result = await api.register({
          company_name: String(form.get("company_name")), name: String(form.get("name")),
          email: String(form.get("email")), phone: String(form.get("phone")),
          password: String(form.get("password")), confirm_password: String(form.get("confirm_password")),
        });
        setLoginId(result.user.login_id);
        return;
      }
      router.push("/"); router.refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Authentication failed"); }
    finally { setLoading(false); }
  }

  async function sso(provider: "google") {
    setError("");
    try { window.location.assign((await api.oauthStart(provider)).authorization_url); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : `${provider} SSO is unavailable`); }
  }

  if (loginId) return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="glass max-w-md rounded-[28px] p-8 text-center">
        <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-emerald-100 text-emerald-700"><ShieldCheck /></div>
        <h1 className="mt-5 text-2xl font-semibold tracking-tight">Your account is ready</h1>
        <p className="mt-2 text-sm text-[#737b87]">Your system-generated login ID is:</p>
        <div className="mono my-5 rounded-xl bg-[#17191f] px-4 py-3 text-sm font-semibold tracking-wider text-white">{loginId}</div>
        <p className="text-xs text-[#8a919c]">Keep this ID. You can sign in with either the ID or your email address.</p>
        <button onClick={() => { router.push("/"); router.refresh(); }} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-[#765cf4] py-3 text-sm font-semibold text-white">Continue to Aurora <ArrowRight size={15} /></button>
      </section>
    </main>
  );

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">
      <section className="relative hidden overflow-hidden bg-[#15171d] p-12 text-white lg:flex lg:flex-col">
        <div className="absolute -left-24 top-1/3 size-96 rounded-full bg-violet-600/20 blur-3xl" /><div className="absolute -right-20 top-0 size-80 rounded-full bg-emerald-400/10 blur-3xl" />
        <div className="relative flex items-center gap-3"><div className="grid size-10 place-items-center rounded-xl bg-white text-lg font-bold text-[#17191f]">A</div><div><p className="font-semibold">Aurora HR</p><p className="text-[10px] tracking-[.18em] text-white/45">AUTONOMOUS WORKFORCE OS</p></div></div>
        <div className="relative my-auto max-w-xl"><div className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-violet-300"><Sparkles size={14} />Private. Intelligent. Accountable.</div><h2 className="text-5xl font-semibold leading-[1.08] tracking-[-.05em]">Your people operations,<br /><span className="text-white/35">working autonomously.</span></h2><p className="mt-6 max-w-md text-sm leading-6 text-white/55">Attendance, leave, payroll, onboarding, policy intelligence, and workforce insights—secured by role-based access and auditable AI.</p></div>
        <p className="relative text-[10px] text-white/30">© 2026 Aurora HR · Local-first AI</p>
      </section>
      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-[430px]">
          <div className="mb-8 lg:hidden"><p className="text-lg font-semibold">Aurora HR</p></div>
          <p className="text-xs font-semibold uppercase tracking-[.16em] text-violet-600">{mode === "login" ? "Welcome back" : "Create your workspace"}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-.04em]">{mode === "login" ? "Sign in to Aurora" : "Start with Aurora HR"}</h1>
          <p className="mt-2 text-sm text-[#7a828e]">{mode === "login" ? "Use your generated login ID or work email." : "The first member of a company becomes its administrator."}</p>
          <div className="mt-7 grid gap-3">
            <SsoButton onClick={() => void sso("google")} icon="G">Google</SsoButton>
          </div>
          <div className="my-6 flex items-center gap-3 text-[10px] uppercase tracking-widest text-[#a0a6ae]"><span className="h-px flex-1 bg-black/[.08]" />or continue with password<span className="h-px flex-1 bg-black/[.08]" /></div>
          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && <><Field name="company_name" label="Company name" placeholder="Aurora Labs" /><Field name="name" label="Full name" placeholder="Aniket Mishra" /><div className="grid grid-cols-2 gap-3"><Field name="email" type="email" label="Work email" placeholder="you@company.com" /><Field name="phone" type="tel" label="Phone" placeholder="+91 98765 43210" /></div></>}
            {mode === "login" && <Field name="login" label="Login ID or email" placeholder="AUANMI20260001" />}
            {mode === "login" && <div className="flex gap-2 rounded-xl border border-black/[.08] bg-white/70 p-1"><button type="button" onClick={() => setRole("employee")} className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold ${role === "employee" ? "bg-[#17191f] text-white" : "text-[#6b7280]"}`}>Employee</button><button type="button" onClick={() => setRole("admin")} className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold ${role === "admin" ? "bg-[#17191f] text-white" : "text-[#6b7280]"}`}>Admin</button></div>}
            <div className={mode === "register" ? "grid grid-cols-2 gap-3" : ""}>
              <PasswordField name="password" label="Password" show={showPassword} onToggle={() => setShowPassword((value) => !value)} />
              {mode === "register" && <PasswordField name="confirm_password" label="Confirm password" show={showPassword} onToggle={() => setShowPassword((value) => !value)} />}
            </div>
            {error && <p role="alert" className="rounded-xl bg-red-50 px-3 py-2.5 text-xs text-red-700">{error}</p>}
            <button disabled={loading} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#17191f] py-3 text-sm font-semibold text-white transition hover:bg-[#765cf4] disabled:opacity-60">{loading && <Loader2 size={15} className="animate-spin" />}{mode === "login" ? "Sign in" : "Create account"}<ArrowRight size={15} /></button>
          </form>
          <p className="mt-6 text-center text-xs text-[#858c97]">{mode === "login" ? "New to Aurora?" : "Already have an account?"} <Link className="font-semibold text-violet-700" href={mode === "login" ? "/register" : "/login"}>{mode === "login" ? "Create an account" : "Sign in"}</Link></p>
          {mode === "login" && <div className="mt-5 rounded-xl border border-violet-100 bg-violet-50/60 p-3 text-[10px] leading-5 text-violet-800"><b>Demo administrator:</b> admin@aurorahr.example.com · Aurora@123</div>}
        </div>
      </section>
    </main>
  );
}

function Field({ name, label, type = "text", placeholder }: { name: string; label: string; type?: string; placeholder: string }) {
  return <label className="block"><span className="mb-1.5 block text-xs font-medium text-[#5d6470]">{label}</span><input required name={name} type={type} placeholder={placeholder} className="w-full rounded-xl border border-black/[.09] bg-white/75 px-3.5 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100" /></label>;
}
function PasswordField({ name, label, show, onToggle }: { name: string; label: string; show: boolean; onToggle: () => void }) {
  return <label className="block"><span className="mb-1.5 block text-xs font-medium text-[#5d6470]">{label}</span><div className="relative"><input required minLength={8} maxLength={72} name={name} type={show ? "text" : "password"} placeholder="Minimum 8 characters" className="w-full rounded-xl border border-black/[.09] bg-white/75 px-3.5 py-3 pr-10 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100" /><button type="button" onClick={onToggle} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#969ca5]" aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff size={15} /> : <Eye size={15} />}</button></div></label>;
}
function SsoButton({ icon, children, onClick }: { icon: string; children: ReactNode; onClick: () => void }) {
  return <button type="button" onClick={onClick} className="flex items-center justify-center gap-2 rounded-xl border border-black/[.09] bg-white/80 py-2.5 text-xs font-semibold transition hover:border-violet-300 hover:shadow-sm"><span className="grid size-5 place-items-center rounded bg-[#f1f2f5] text-[10px] font-bold">{icon}</span>{children}</button>;
}
