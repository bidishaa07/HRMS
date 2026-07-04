"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Clock3, Loader2, LogIn, LogOut } from "lucide-react";
import { api, ApiError, type Attendance, type User } from "@/lib/api";
import { Card, Pill } from "../ui";

export function AttendanceView({ user }: { user: User }) {
  const [rows, setRows] = useState<Attendance[]>([]);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  async function load() { setLoading(true); try { setRows(await api.attendance(month)); } finally { setLoading(false); } }
  useEffect(() => { setLoading(true); api.attendance(month).then(setRows).finally(() => setLoading(false)); }, [month]);
  async function action(kind: "in" | "out") {
    setMessage("");
    try { const result = kind === "in" ? await api.checkIn() : await api.checkOut(); setMessage(result.message); await load(); }
    catch (reason) { setMessage(reason instanceof ApiError ? reason.message : "Attendance action failed"); }
  }
  function moveMonth(delta: number) { const [year, value] = month.split("-").map(Number); const next = new Date(year, value - 1 + delta, 1); setMonth(next.toISOString().slice(0, 7)); }
  const mineToday = rows.find((row) => row.employee_id === user.employee_id && row.date === new Date().toISOString().slice(0,10));
  const totalMinutes = rows.reduce((sum, row) => sum + row.work_minutes, 0);
  return <div className="space-y-5">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">Time tracking</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Attendance</h2><p className="mt-1 text-xs text-[#858c97]">{user.role === "employee" ? "Your monthly attendance and working hours." : "Organization-wide attendance with employee-level detail."}</p></div><div className="flex gap-2"><button disabled={Boolean(mineToday?.check_in)} onClick={() => void action("in")} className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-40"><LogIn size={14} />Check in</button><button disabled={!mineToday?.check_in || Boolean(mineToday?.check_out)} onClick={() => void action("out")} className="flex items-center gap-2 rounded-xl bg-[#17191f] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-40"><LogOut size={14} />Check out</button></div></div>
    {message && <p className="rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{message}</p>}
    <div className="grid gap-3 sm:grid-cols-3"><Stat icon={<CheckCircle2 size={15} />} label="Days present" value={String(new Set(rows.map((row) => row.date)).size)} /><Stat icon={<Clock3 size={15} />} label="Hours recorded" value={`${(totalMinutes / 60).toFixed(1)}h`} /><Stat icon={<LogIn size={15} />} label="Late arrivals" value={String(rows.filter((row) => row.status === "late").length)} /></div>
    <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-black/[.06] p-4"><button onClick={() => moveMonth(-1)} className="grid size-8 place-items-center rounded-lg bg-black/[.04]" aria-label="Previous month"><ArrowLeft size={14} /></button><input value={month} onChange={(event) => setMonth(event.target.value)} type="month" className="rounded-lg border border-black/[.08] bg-white px-3 py-1.5 text-xs" /><button onClick={() => moveMonth(1)} className="grid size-8 place-items-center rounded-lg bg-black/[.04]" aria-label="Next month"><ArrowRight size={14} /></button></div>
      {loading ? <div className="grid h-48 place-items-center"><Loader2 className="animate-spin text-violet-600" /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left"><thead><tr className="border-b border-black/[.05] text-[9px] uppercase tracking-wider text-[#969ca5]"><th className="p-4">Employee</th><th>Date</th><th>Check in</th><th>Check out</th><th>Work hours</th><th>Extra</th><th>Status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-b border-black/[.045] last:border-0"><td className="p-4 text-xs font-medium">{row.employee_name}</td><td className="text-[10px] text-[#737b87]">{formatDate(row.date)}</td><td className="mono text-[10px]">{formatTime(row.check_in)}</td><td className="mono text-[10px]">{formatTime(row.check_out)}</td><td className="mono text-[10px]">{formatMinutes(row.work_minutes)}</td><td className="mono text-[10px]">{formatMinutes(row.extra_minutes)}</td><td><Pill tone={row.status === "present" ? "green" : "amber"}>{row.status}</Pill></td></tr>)}</tbody></table>{rows.length === 0 && <p className="p-10 text-center text-xs text-[#9298a1]">No attendance records for this month.</p>}</div>}
    </Card>
  </div>;
}
function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <Card className="p-4"><div className="flex items-center gap-2 text-violet-600">{icon}<span className="text-[10px] text-[#858c97]">{label}</span></div><p className="mt-2 text-2xl font-semibold">{value}</p></Card>; }
function formatDate(value: string) { return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }); }
function formatTime(value?: string) { return value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"; }
function formatMinutes(value: number) { return `${Math.floor(value / 60).toString().padStart(2,"0")}:${(value % 60).toString().padStart(2,"0")}`; }
