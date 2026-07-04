"use client";

import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, KeyRound, Save, ShieldCheck, XCircle } from "lucide-react";
import { api, ApiError, type User } from "@/lib/api";
import { Card, Pill } from "../ui";

export function SettingsView({ user, onUserChange }: { user: User; onUserChange: (user: User) => void }) {
  const [providers, setProviders] = useState({ google: false });
  const [message, setMessage] = useState("");
  useEffect(() => { api.providerStatus().then(setProviders); }, []);
  async function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    try { const updated = await api.updateProfile({ name: String(data.get("name")), phone: String(data.get("phone")) }); onUserChange(updated); setMessage("Profile saved."); }
    catch (reason) { setMessage(reason instanceof ApiError ? reason.message : "Profile update failed"); }
  }
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    try { await api.changePassword({ current_password: String(data.get("current_password")), new_password: String(data.get("new_password")) }); setMessage("Password changed. Sign in again to start a new session."); event.currentTarget.reset(); }
    catch (reason) { setMessage(reason instanceof ApiError ? reason.message : "Password change failed"); }
  }
  return <div className="space-y-5"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">Account controls</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Settings</h2><p className="mt-1 text-xs text-[#858c97]">Profile, password security, and enterprise identity providers.</p></div>{message && <p className="rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{message}</p>}<div className="grid gap-5 lg:grid-cols-2"><Card className="p-5"><div className="flex items-center gap-2"><ShieldCheck size={16} className="text-violet-600" /><h3 className="text-sm font-semibold">Profile</h3></div><form onSubmit={updateProfile} className="mt-5 space-y-3"><Field name="name" label="Full name" defaultValue={user.name} /><Field name="phone" label="Phone" defaultValue={user.phone ?? ""} /><label className="block text-xs">Login ID<input readOnly value={user.login_id} className="mono mt-1 w-full rounded-xl border border-black/[.06] bg-black/[.03] p-3 text-xs" /></label><button className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#17191f] py-3 text-xs font-semibold text-white"><Save size={13} />Save profile</button></form></Card><Card className="p-5"><div className="flex items-center gap-2"><KeyRound size={16} className="text-violet-600" /><h3 className="text-sm font-semibold">Change password</h3></div><form onSubmit={changePassword} className="mt-5 space-y-3"><Field name="current_password" label="Current password" type="password" /><Field name="new_password" label="New password" type="password" /><button className="w-full rounded-xl bg-[#17191f] py-3 text-xs font-semibold text-white">Update password</button></form></Card></div><Card className="p-5"><h3 className="text-sm font-semibold">OAuth 2.0 providers</h3><p className="mt-1 text-[10px] text-[#858c97]">Provider buttons activate when both client ID and client secret are loaded by the API.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><Provider name="Google SSO" ready={providers.google} /></div></Card></div>;
}
function Field({ name, label, defaultValue = "", type = "text" }: { name: string; label: string; defaultValue?: string; type?: string }) { return <label className="block text-xs">{label}<input required minLength={type === "password" ? 8 : undefined} maxLength={type === "password" ? 72 : undefined} name={name} type={type} defaultValue={defaultValue} className="mt-1 w-full rounded-xl border border-black/[.09] bg-white p-3 text-sm" /></label>; }
function Provider({ name, ready }: { name: string; ready: boolean }) { return <div className="flex items-center gap-3 rounded-xl border border-black/[.06] bg-white/60 p-3">{ready ? <CheckCircle2 size={16} className="text-emerald-600" /> : <XCircle size={16} className="text-amber-600" />}<div><p className="text-xs font-medium">{name}</p><Pill tone={ready ? "green" : "amber"}>{ready ? "Configured" : "Credentials missing"}</Pill></div></div>; }
