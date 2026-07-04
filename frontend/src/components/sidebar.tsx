"use client";

import { Activity, Bot, Building2, CalendarDays, FileText, LayoutDashboard, LogOut, Settings, Users, WalletCards, X } from "lucide-react";
import { clsx } from "clsx";
import type { User } from "@/lib/api";

export const navigation = [
  ["Overview", LayoutDashboard], ["People", Users], ["Attendance", Activity], ["Leave", CalendarDays],
  ["Payroll", WalletCards], ["Documents", FileText], ["Organization", Building2], ["AI workforce", Bot],
] as const;

export function Sidebar({ active, user, mobileOpen, onNavigate, onClose, onLogout }: { active: string; user: User; mobileOpen: boolean; onNavigate: (item: string) => void; onClose: () => void; onLogout: () => void }) {
  const navigate = (item: string) => { onNavigate(item); onClose(); };
  return <>{mobileOpen && <button className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm lg:hidden" onClick={onClose} aria-label="Close navigation overlay" />}<aside className={clsx("fixed inset-y-0 left-0 z-40 flex w-[244px] flex-col border-r border-black/[.06] bg-white/80 p-5 backdrop-blur-3xl transition-transform lg:translate-x-0", mobileOpen ? "translate-x-0" : "-translate-x-full")}><div className="mb-8 flex items-center gap-3 px-2"><div className="grid size-9 place-items-center rounded-xl bg-[#17191f] text-sm font-semibold text-white shadow-lg">A</div><div><p className="text-[15px] font-semibold tracking-tight">Aurora HR</p><p className="text-[10px] text-[#8b919c]">WORKFORCE OS</p></div><button onClick={onClose} className="ml-auto lg:hidden" aria-label="Close navigation"><X size={16} /></button></div><nav className="space-y-1" aria-label="Primary navigation">{navigation.map(([label, Icon]) => <button key={label} onClick={() => navigate(label)} className={clsx("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[13px] transition", active === label ? "bg-[#17191f] text-white shadow-lg" : "text-[#68707d] hover:bg-white hover:text-[#17191f]")}><Icon size={16} strokeWidth={1.8} /><span>{label}</span>{label === "AI workforce" && <span className="ml-auto size-1.5 rounded-full bg-emerald-400" />}</button>)}</nav><div className="mt-auto border-t border-black/[.06] pt-4"><button onClick={() => navigate("Settings")} className={clsx("mb-2 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px]", active === "Settings" ? "bg-[#17191f] text-white" : "text-[#68707d] hover:bg-white")}><Settings size={16} />Settings</button><div className="rounded-2xl bg-white/80 p-2.5"><div className="flex items-center gap-3"><div className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-violet-200 to-pink-200 text-[10px] font-semibold">{user.name.split(" ").map((part) => part[0]).slice(0,2).join("")}</div><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium">{user.name}</p><p className="truncate text-[9px] text-[#8b919c]">{user.login_id} · {user.role}</p></div><button onClick={onLogout} title="Log out" className="text-[#9aa0aa]"><LogOut size={14} /></button></div></div></div></aside></>;
}

