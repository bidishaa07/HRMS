"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Check, ChevronDown, Clock3, Loader2, Menu, UserRound } from "lucide-react";
import { api, ApiError, type Notification, type User } from "@/lib/api";
import { Sidebar } from "./sidebar";
import { OverviewView } from "./modules/overview-view";
import { PeopleView } from "./modules/people-view";
import { AttendanceView } from "./modules/attendance-view";
import { LeaveView } from "./modules/leave-view";
import { PayrollView } from "./modules/payroll-view";
import { DocumentsView } from "./modules/documents-view";
import { OrganizationView } from "./modules/organization-view";
import { AgentsView } from "./modules/agents-view";
import { SettingsView } from "./modules/settings-view";

export function AuroraApp() {
  const router = useRouter(); const [user, setUser] = useState<User | null>(null); const [active, setActive] = useState("Overview");
  const [mobileOpen, setMobileOpen] = useState(false); const [profileOpen, setProfileOpen] = useState(false); const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]); const [attendanceMessage, setAttendanceMessage] = useState("");
  const [checkedIn, setCheckedIn] = useState(false); const [checkedOut, setCheckedOut] = useState(false);

  useEffect(() => {
    api.me().then((nextUser) => { setUser(nextUser); return Promise.all([nextUser, api.notifications(), api.attendance(new Date().toISOString().slice(0,7))] as const); })
      .then(([nextUser, items, attendance]) => { setNotifications(items); const today = attendance.find((row) => row.employee_id === nextUser.employee_id && row.date === new Date().toISOString().slice(0,10)); setCheckedIn(Boolean(today?.check_in)); setCheckedOut(Boolean(today?.check_out)); })
      .catch((reason) => { if (reason instanceof ApiError && reason.status === 401) router.replace("/login"); });
  }, [router]);

  async function logout() { await api.logout().catch(() => undefined); window.location.assign("/login"); }
  async function attendanceAction() { setAttendanceMessage(""); try { const result = !checkedIn ? await api.checkIn() : await api.checkOut(); setAttendanceMessage(result.message); if (!checkedIn) setCheckedIn(true); else setCheckedOut(true); } catch (reason) { setAttendanceMessage(reason instanceof ApiError ? reason.message : "Attendance action failed"); } }
  async function readNotification(item: Notification) { if (!item.read) { await api.readNotification(item.id); setNotifications((items) => items.map((entry) => entry.id === item.id ? { ...entry, read: true } : entry)); } }

  if (!user) return <div className="grid min-h-screen place-items-center"><div className="text-center"><Loader2 className="mx-auto animate-spin text-violet-600" /><p className="mt-3 text-xs text-[#858c97]">Verifying secure session…</p></div></div>;
  const views: Record<string, React.ReactNode> = {
    Overview: <OverviewView user={user} onNavigate={setActive} />, People: <PeopleView user={user} />,
    Attendance: <AttendanceView user={user} />, Leave: <LeaveView user={user} />,
    Payroll: <PayrollView user={user} />, Documents: <DocumentsView />,
    Organization: <OrganizationView />, "AI workforce": <AgentsView />,
    Settings: <SettingsView user={user} onUserChange={setUser} />,
  };
  return <div className="min-h-screen lg:pl-[244px]"><Sidebar active={active} user={user} mobileOpen={mobileOpen} onNavigate={setActive} onClose={() => setMobileOpen(false)} onLogout={() => void logout()} /><main className="mx-auto max-w-[1560px] px-4 py-4 sm:px-6 lg:px-8 lg:py-6"><header className="relative z-20 mb-7 flex items-center justify-between"><div className="flex items-center gap-3"><button onClick={() => setMobileOpen(true)} className="grid size-10 place-items-center rounded-xl bg-white lg:hidden" aria-label="Open navigation"><Menu size={18} /></button><div><p className="mb-1 text-[10px] font-medium uppercase tracking-[.16em] text-[#9197a1]">{new Date().toLocaleDateString("en-IN", { weekday: "long", month: "long", day: "numeric", timeZone: "Asia/Kolkata" })}</p><h1 className="text-[24px] font-semibold tracking-[-.04em] sm:text-[28px]">{active === "Overview" ? `${indianGreeting()}, ${user.name.split(" ")[0]}.` : active}</h1></div></div><div className="flex items-center gap-2">
    <div className="relative"><button onClick={() => { setNotificationsOpen((value) => !value); setProfileOpen(false); }} className="relative grid size-10 place-items-center rounded-xl border border-black/[.06] bg-white/70 text-[#5c6370]" aria-label="Notifications"><Bell size={17} />{notifications.some((item) => !item.read) && <span className="absolute right-2 top-2 size-1.5 rounded-full bg-[#765cf4]" />}</button>{notificationsOpen && <div className="absolute right-0 top-12 w-80 rounded-2xl border border-black/[.06] bg-white p-3 shadow-2xl"><p className="px-2 py-1 text-xs font-semibold">Notifications</p><div className="mt-2 max-h-72 overflow-auto">{notifications.map((item) => <button key={item.id} onClick={() => void readNotification(item)} className="w-full rounded-xl p-2 text-left hover:bg-black/[.03]"><div className="flex items-center gap-2"><span className={`size-1.5 rounded-full ${item.read ? "bg-transparent" : "bg-violet-500"}`} /><p className="text-[10px] font-semibold">{item.title}</p></div><p className="mt-1 pl-3.5 text-[9px] leading-4 text-[#858c97]">{item.body}</p></button>)}{!notifications.length && <p className="p-4 text-center text-[10px] text-[#9298a1]">No notifications</p>}</div></div>}</div>
    <button disabled={checkedOut} onClick={() => void attendanceAction()} className="hidden items-center gap-2 rounded-xl bg-[#17191f] px-4 py-2.5 text-xs font-semibold text-white shadow-lg disabled:opacity-50 sm:flex">{checkedIn ? <Check size={15} /> : <Clock3 size={15} />}{checkedOut ? "Checked out" : checkedIn ? "Check out" : "Check in"}</button>
    <div className="relative"><button onClick={() => { setProfileOpen((value) => !value); setNotificationsOpen(false); }} className="flex items-center gap-2 rounded-xl border border-black/[.06] bg-white/70 p-1.5 pr-2 text-xs"><div className="grid size-7 place-items-center rounded-lg bg-violet-100 text-violet-700"><UserRound size={14} /></div><ChevronDown size={12} /></button>{profileOpen && <div className="absolute right-0 top-12 w-56 rounded-2xl border border-black/[.06] bg-white p-3 shadow-2xl"><p className="text-xs font-semibold">{user.name}</p><p className="mt-1 text-[9px] text-[#8b929d]">{user.email}</p><p className="mono mt-2 rounded-lg bg-black/[.035] p-2 text-[9px]">{user.login_id}</p><button onClick={() => setActive("People")} className="mt-2 w-full rounded-lg px-2 py-2 text-left text-[10px] hover:bg-black/[.04]">My profile</button><button onClick={() => void logout()} className="w-full rounded-lg px-2 py-2 text-left text-[10px] text-red-600 hover:bg-red-50">Log out</button></div>}</div></div></header>{attendanceMessage && <div className="mb-4 rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{attendanceMessage}</div>}{views[active]}<footer className="flex flex-col items-center justify-between gap-2 py-7 text-[9px] text-[#9ca2ab] sm:flex-row"><p>Aurora HR · Private AI workforce operating system</p><p className="mono">JWT SECURED · AUDIT ENABLED</p></footer></main></div>;
}

function indianGreeting() {
  const hour = Number(new Intl.DateTimeFormat("en-IN", { hour: "numeric", hour12: false, timeZone: "Asia/Kolkata" }).format(new Date()));
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good night";
}
