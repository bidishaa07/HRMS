"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Check, Loader2, Plus, Radio, X } from "lucide-react";
import { api, ApiError, type User } from "@/lib/api";
import { useLeaveRealtime, type RealtimeStatus } from "@/lib/realtime";
import { Modal } from "../modal";
import { Card, Pill } from "../ui";

const leaveKey = ["leaves"];

export function LeaveView({ user }: { user: User }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const status = useLeaveRealtime();
  const leavesQuery = useQuery({ queryKey: leaveKey, queryFn: api.leaves });
  const applyMutation = useMutation({
    mutationFn: api.applyLeave,
    onSuccess: async () => {
      setOpen(false);
      setMessage("");
      await queryClient.invalidateQueries({ queryKey: leaveKey });
    },
    onError: (reason) => setMessage(reason instanceof ApiError ? reason.message : "Could not apply for leave"),
  });
  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approved" | "rejected" }) => api.decideLeave(id, decision),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: leaveKey });
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (reason) => setMessage(reason instanceof ApiError ? reason.message : "Decision failed"),
  });
  const leaves = leavesQuery.data ?? [];

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    applyMutation.mutate({
      leave_type: String(data.get("leave_type")),
      start_date: String(data.get("start_date")),
      end_date: String(data.get("end_date")),
      remarks: String(data.get("remarks")),
    });
    event.currentTarget.reset();
  }

  return <div className="space-y-5"><div className="flex items-end justify-between"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">Time off</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Leave management</h2><p className="mt-1 text-xs text-[#858c97]">{user.role === "employee" ? "Apply for leave and track every decision." : "Review, approve, and reject employee requests."}</p></div><div className="flex items-center gap-3"><RealtimeBadge status={status} /><button onClick={() => setOpen(true)} className="flex items-center gap-2 rounded-xl bg-[#17191f] px-4 py-2.5 text-xs font-semibold text-white"><Plus size={14} />New request</button></div></div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><Balance name="Paid time off" days="24" tone="violet" /><Balance name="Sick time off" days="07" tone="green" /><Balance name="Casual leave" days="08" tone="amber" /><Balance name="Unpaid leave" days="∞" tone="neutral" /></div>
    {message && <p className="rounded-xl bg-red-50 p-3 text-xs text-red-700">{message}</p>}
    <Card className="overflow-hidden">{leavesQuery.isLoading ? <div className="grid h-48 place-items-center"><Loader2 className="animate-spin text-violet-600" /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left"><thead><tr className="border-b border-black/[.05] text-[9px] uppercase tracking-wider text-[#969ca5]"><th className="p-4">Employee</th><th>Start</th><th>End</th><th>Type</th><th>Days</th><th>Status</th>{user.role === "admin" && <th>Decision</th>}</tr></thead><tbody>{leaves.map((leave) => <tr key={leave.id} className="border-b border-black/[.045] last:border-0"><td className="p-4"><p className="text-xs font-medium">{leave.employee_name}</p><p className="mt-0.5 max-w-[190px] truncate text-[9px] text-[#9298a1]">{leave.remarks}</p></td><td className="text-[10px]">{leave.start_date}</td><td className="text-[10px]">{leave.end_date}</td><td className="text-[10px]">{leave.leave_type}</td><td className="mono text-[10px]">{leave.days}</td><td><Pill tone={leave.status === "approved" ? "green" : leave.status === "rejected" ? "neutral" : "amber"}>{leave.status}</Pill></td>{user.role === "admin" && <td><div className="flex gap-1"><button disabled={leave.status !== "pending" || decideMutation.isPending} onClick={() => decideMutation.mutate({ id: leave.id, decision: "approved" })} title="Approve" className="grid size-7 place-items-center rounded-lg bg-emerald-100 text-emerald-700 disabled:opacity-30"><Check size={12} /></button><button disabled={leave.status !== "pending" || decideMutation.isPending} onClick={() => decideMutation.mutate({ id: leave.id, decision: "rejected" })} title="Reject" className="grid size-7 place-items-center rounded-lg bg-red-100 text-red-700 disabled:opacity-30"><X size={12} /></button></div></td>}</tr>)}</tbody></table>{!leaves.length && <p className="p-10 text-center text-xs text-[#9298a1]">No leave requests yet.</p>}</div>}</Card>
    <Modal open={open} onClose={() => { setOpen(false); setMessage(""); }} title="Request time off" description="Aurora checks dates and prevents overlapping requests."><form onSubmit={apply} className="space-y-4"><label className="block text-xs">Leave type<select name="leave_type" className="mt-1 w-full rounded-xl border border-black/[.09] bg-white p-3"><option>Paid</option><option>Sick</option><option>Casual</option><option>Unpaid</option></select></label><div className="grid grid-cols-2 gap-3"><label className="text-xs">Start date<input required name="start_date" type="date" className="mt-1 w-full rounded-xl border border-black/[.09] bg-white p-3" /></label><label className="text-xs">End date<input required name="end_date" type="date" className="mt-1 w-full rounded-xl border border-black/[.09] bg-white p-3" /></label></div><label className="block text-xs">Remarks<textarea required minLength={3} name="remarks" className="mt-1 min-h-24 w-full rounded-xl border border-black/[.09] bg-white p-3" /></label>{message && <p className="rounded-xl bg-red-50 p-3 text-xs text-red-700">{message}</p>}<button disabled={applyMutation.isPending} className="w-full rounded-xl bg-[#17191f] py-3 text-xs font-semibold text-white disabled:opacity-50">{applyMutation.isPending ? "Submitting..." : "Submit request"}</button></form></Modal>
  </div>;
}

function RealtimeBadge({ status }: { status: RealtimeStatus }) {
  const label = status === "connected" ? "Live" : status === "connecting" ? "Connecting" : status === "offline" ? "Offline" : "Reconnecting";
  return <span className="hidden items-center gap-1.5 text-[10px] font-semibold text-[#7b828d] sm:flex"><Radio size={12} className={status === "connected" ? "text-emerald-500" : "text-amber-500"} />{label}</span>;
}

function Balance({ name, days, tone }: { name: string; days: string; tone: "violet" | "green" | "amber" | "neutral" }) { return <Card className="p-4"><CalendarDays size={14} className="text-violet-600" /><p className="mt-3 text-[10px] text-[#858c97]">{name}</p><p className="mt-1 text-2xl font-semibold">{days}<span className="ml-1 text-[9px] font-normal text-[#989ea7]">days</span></p><Pill tone={tone}>Available</Pill></Card>; }
