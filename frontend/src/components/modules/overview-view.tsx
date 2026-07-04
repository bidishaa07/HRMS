"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Bot, CalendarDays, Check, HeartPulse, Loader2, Sparkles, Users, WalletCards } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Employee, type Summary, type User } from "@/lib/api";
import { Modal } from "../modal";
import { Card, Pill } from "../ui";

const trend = [{ day: "Mon", present: 42 }, { day: "Tue", present: 45 }, { day: "Wed", present: 44 }, { day: "Thu", present: 41 }, { day: "Fri", present: 43 }];

export function OverviewView({ onNavigate }: { user: User; onNavigate: (item: string) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [people, setPeople] = useState<Employee[]>([]);
  const [selectedMetric, setSelectedMetric] = useState<{ label: string; value: string | number; note: string } | null>(null);

  useEffect(() => {
    Promise.all([api.summary(), api.employees()]).then(([nextSummary, nextPeople]) => {
      setSummary(nextSummary);
      setPeople(nextPeople.slice(0, 5));
    });
  }, []);

  if (!summary) return <div className="grid h-[60vh] place-items-center"><Loader2 className="animate-spin text-violet-600" /></div>;

  const metrics = [
    { label: "Total employees", value: summary.employees, note: "Active workforce", icon: Users, color: "#765cf4" },
    { label: "Present today", value: summary.present_today, note: `${Math.round(summary.present_today / Math.max(1, summary.employees) * 100)}% attendance`, icon: Check, color: "#47c6a4" },
    { label: "Pending approvals", value: summary.pending_approvals, note: "Needs HR review", icon: CalendarDays, color: "#f4a261" },
    { label: "Workforce health", value: `${summary.organization_health}/100`, note: `${summary.burnout_alerts} risk signals`, icon: HeartPulse, color: "#e76f9c" },
  ];

  return <div className="space-y-5">
    <section className="overflow-hidden rounded-[26px] bg-[#17191f] text-white shadow-[0_22px_60px_rgba(22,18,44,.18)]">
      <div className="relative grid min-h-[190px] gap-6 p-7 lg:grid-cols-[1fr_420px] lg:items-center">
        <div className="absolute -right-10 -top-32 size-[330px] rounded-full bg-violet-500/25 blur-3xl" />
        <div className="relative">
          <div className="mb-3 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.18em] text-violet-300">
            <Sparkles size={13} />Executive morning brief
          </div>
          <h2 className="text-2xl font-medium tracking-tight">
            {summary.organization_health >= 80 ? "Your organization is healthy." : "Your organization needs attention."}
            <br />
            <span className="text-white/45">{summary.pending_approvals} approvals need review.</span>
          </h2>
          <div className="mt-5 flex flex-wrap gap-4 text-[11px] text-white/55">
            <span><b className="mr-1 text-white">{summary.present_today}</b>present</span>
            <span><b className="mr-1 text-white">{summary.on_leave}</b>on leave</span>
            <span><b className="mr-1 text-amber-300">{summary.late_arrivals}</b>late</span>
          </div>
        </div>
        <div className="relative rounded-2xl border border-white/10 bg-white/[.055] p-4">
          <div className="flex items-center justify-between">
            <p className="text-[11px] text-white/55">Aurora recommends</p>
            <Pill tone="violet">Live insight</Pill>
          </div>
          <p className="mt-3 text-sm leading-6 text-white/80">
            Review {summary.pending_approvals} leave requests and follow up on {summary.burnout_alerts} workforce health signals.
          </p>
          <button onClick={() => onNavigate("Leave")} className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-violet-300">
            Review requests <ArrowRight size={11} />
          </button>
        </div>
      </div>
    </section>

    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {metrics.map((metric) => (
        <button key={metric.label} type="button" onClick={() => setSelectedMetric({ label: metric.label, value: metric.value, note: metric.note })} className="text-left">
          <Card className="p-5">
            <div className="grid size-8 place-items-center rounded-xl" style={{ background: `${metric.color}16`, color: metric.color }}>
              <metric.icon size={16} />
            </div>
            <p className="mt-4 text-[10px] text-[#858c97]">{metric.label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight">{metric.value}</p>
            <p className="mt-1 text-[9px] text-[#989ea7]">{metric.note}</p>
          </Card>
        </button>
      ))}
    </div>

    <div className="grid gap-5 xl:grid-cols-[1.2fr_.8fr]">
      <Card className="p-5">
        <div className="mb-5">
          <h3 className="text-sm font-semibold">Attendance pulse</h3>
          <p className="text-[9px] text-[#9298a1]">Last five working days</p>
        </div>
        <div className="h-56">
          <ResponsiveContainer>
            <AreaChart data={trend} margin={{ left: -20, right: 8 }}>
              <defs>
                <linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stopColor="#765cf4" stopOpacity={0.3} />
                  <stop offset="1" stopColor="#765cf4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="rgba(0,0,0,.05)" />
              <XAxis dataKey="day" axisLine={false} tickLine={false} fontSize={9} />
              <YAxis domain={[0, 50]} axisLine={false} tickLine={false} fontSize={9} />
              <Tooltip />
              <Area dataKey="present" type="monotone" stroke="#765cf4" strokeWidth={2} fill="url(#fill)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Quick actions</h3>
            <p className="text-[9px] text-[#9298a1]">Working HR workflows</p>
          </div>
          <Bot size={16} className="text-violet-600" />
        </div>
        <div className="mt-5 grid gap-2">
          {[
            { label: "Open people directory", target: "People", icon: Users },
            { label: "Review time off", target: "Leave", icon: CalendarDays },
            { label: "View payroll", target: "Payroll", icon: WalletCards },
            { label: "Ask Aurora", target: "AI workforce", icon: Bot },
          ].map(({ label, target, icon: Icon }) => (
            <button key={target} onClick={() => onNavigate(target)} className="flex items-center gap-3 rounded-xl border border-black/[.06] bg-white/60 p-3 text-left text-[10px] font-medium transition hover:border-violet-200 hover:shadow-sm">
              <span className="grid size-7 place-items-center rounded-lg bg-violet-50 text-violet-700"><Icon size={12} /></span>
              {label}
              <ArrowRight size={11} className="ml-auto" />
            </button>
          ))}
        </div>
      </Card>
    </div>

    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-black/[.05] p-5">
        <div>
          <h3 className="text-sm font-semibold">People at work</h3>
          <p className="text-[9px] text-[#9298a1]">Current presence from persisted attendance</p>
        </div>
        <button onClick={() => onNavigate("People")} className="text-[10px] font-semibold text-violet-700">View all</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] text-left">
          <thead>
            <tr className="border-b border-black/[.05] text-[9px] uppercase tracking-wider text-[#969ca5]">
              <th className="p-4">Employee</th>
              <th>Department</th>
              <th>Login ID</th>
              <th>Status</th>
              <th>Health</th>
            </tr>
          </thead>
          <tbody>
            {people.map((person) => (
              <tr key={person.id} className="border-b border-black/[.04]">
                <td className="p-4 text-xs font-medium">{person.name}<p className="text-[9px] font-normal text-[#9298a1]">{person.title}</p></td>
                <td className="text-[10px]">{person.department}</td>
                <td className="mono text-[9px]">{person.employee_code}</td>
                <td><Pill tone={person.status === "present" ? "green" : person.status === "late" ? "amber" : "neutral"}>{person.status}</Pill></td>
                <td className="mono text-[10px]">{person.health_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>

    <Modal open={Boolean(selectedMetric)} onClose={() => setSelectedMetric(null)} title={selectedMetric?.label ?? "Insight"} description="Detailed view from the live HR summary.">
      <div className="rounded-2xl bg-violet-50 p-4 text-sm text-violet-900">
        <p className="text-2xl font-semibold">{selectedMetric?.value}</p>
        <p className="mt-2 text-sm text-violet-700">{selectedMetric?.note}</p>
      </div>
    </Modal>
  </div>;
}
