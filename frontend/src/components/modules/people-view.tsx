"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Loader2, Mail, MapPin, Plus, Search, ShieldCheck } from "lucide-react";
import { api, ApiError, type Employee, type User } from "@/lib/api";
import { useRealtime } from "@/lib/realtime";
import { Modal } from "../modal";
import { Card, Pill } from "../ui";

export function PeopleView({ user }: { user: User }) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedPerson, setSelectedPerson] = useState<Employee | null>(null);
  const [message, setMessage] = useState("");
  const [credentials, setCredentials] = useState<{ loginId: string; password: string } | null>(null);
  const [copied, setCopied] = useState<"login" | "password" | null>(null);
  const [detailMessage, setDetailMessage] = useState("");
  const queryClient = useQueryClient();
  const peopleQuery = useQuery({ queryKey: ["employees", search], queryFn: () => api.employees(search) });
  useRealtime();
  const people = peopleQuery.data ?? [];

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const result = await api.createEmployee({ name: String(data.get("name")), email: String(data.get("email")), phone: String(data.get("phone")), department: String(data.get("department")), title: String(data.get("title")), salary: Number(data.get("salary")), joining_date: String(data.get("joining_date")) });
      setCredentials({ loginId: result.employee_code, password: result.temporary_password });
      setMessage("Employee created successfully");
      form.reset();
      await Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: ["employees"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    } catch (reason) { setMessage(reason instanceof ApiError ? reason.message : "Could not create employee"); }
  }

  async function copyCredential(kind: "login" | "password") {
    if (!credentials) return;
    await navigator.clipboard.writeText(kind === "login" ? credentials.loginId : credentials.password);
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1500);
  }

  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setDetailMessage("");
    if (!selectedPerson) return;
    const data = new FormData(event.currentTarget);
    try {
      const updated = await api.updateEmployee(selectedPerson.id, { name: String(data.get("name")), email: String(data.get("email")), phone: String(data.get("phone")), department: String(data.get("department")), title: String(data.get("title")), salary: Number(data.get("salary")), joining_date: String(data.get("joining_date")) });
      setSelectedPerson(updated); setDetailMessage("Employee updated successfully");
      await queryClient.invalidateQueries({ queryKey: ["employees"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    } catch (reason) { setDetailMessage(reason instanceof ApiError ? reason.message : "Could not update employee"); }
  }

  async function deactivate() {
    if (!selectedPerson || !window.confirm(`Deactivate ${selectedPerson.name}?`)) return;
    try {
      await api.deactivateEmployee(selectedPerson.id);
      setSelectedPerson({ ...selectedPerson, status: "inactive" }); setDetailMessage("Employee deactivated successfully");
      await queryClient.invalidateQueries({ queryKey: ["employees"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    } catch (reason) { setDetailMessage(reason instanceof ApiError ? reason.message : "Could not deactivate employee"); }
  }

  return <div className="space-y-5">
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">People directory</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Employees</h2><p className="mt-1 text-xs text-[#858c97]">Live status, role, department, and workforce health.</p></div>{user.role !== "employee" && <button type="button" onClick={() => setOpen(true)} className="flex items-center justify-center gap-2 rounded-xl bg-[#17191f] px-4 py-2.5 text-xs font-semibold text-white"><Plus size={14} />New employee</button>}</div>
    <Card className="p-4"><form onSubmit={(event) => event.preventDefault()} className="flex items-center gap-2"><Search size={15} className="text-[#949aa4]" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm outline-none" placeholder="Search by name, email, or login ID" /><button type="submit" className="rounded-lg bg-black/[.05] px-3 py-1.5 text-[10px] font-semibold">Search</button></form></Card>
    {peopleQuery.isLoading ? <div className="grid h-48 place-items-center"><Loader2 className="animate-spin text-violet-600" /></div> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{people.map((person) => <button key={person.id} type="button" onClick={() => { setSelectedPerson(person); setDetailOpen(true); }} className="text-left"><Card className="p-5 transition hover:-translate-y-0.5 hover:shadow-xl"><div className="flex items-start justify-between"><div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-violet-100 to-pink-100 text-xs font-bold text-violet-700">{person.name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div><span title={person.status} className={`size-2.5 rounded-full ${person.status === "present" ? "bg-emerald-500" : person.status === "late" ? "bg-amber-400" : person.status === "leave" ? "bg-blue-500" : "bg-rose-400"}`} /></div><h3 className="mt-4 text-sm font-semibold">{person.name}</h3><p className="mt-0.5 text-[10px] text-[#858c97]">{person.title} - {person.department}</p><div className="mt-4 space-y-2 border-t border-black/[.05] pt-4 text-[10px] text-[#737b87]"><p className="flex items-center gap-2"><ShieldCheck size={12} />{person.employee_code}</p><p className="flex items-center gap-2"><Mail size={12} />{person.email}</p><p className="flex items-center gap-2"><MapPin size={12} />{person.location}</p></div><div className="mt-4 flex items-center justify-between"><Pill tone={person.status === "present" ? "green" : person.status === "late" ? "amber" : "neutral"}>{person.status}</Pill><span className="mono text-[9px] text-[#878e99]">Health {person.health_score}/100</span></div></Card></button>)}</div>}
    <Modal open={open} onClose={() => { setOpen(false); setMessage(""); setCredentials(null); setCopied(null); }} title="Add employee" description="Aurora generates the login ID and provisions a temporary password."><form onSubmit={create} className="grid gap-3 sm:grid-cols-2">{!credentials && <><FormField name="name" label="Full name" /><FormField name="email" label="Email" type="email" /><FormField name="phone" label="Phone" /><FormField name="department" label="Department" /><FormField name="title" label="Job title" /><FormField name="salary" label="Monthly salary" type="number" /><FormField name="joining_date" label="Joining date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} /></>}{message && <p className={`sm:col-span-2 rounded-xl p-3 text-xs ${credentials ? "bg-emerald-50 text-emerald-800" : "bg-violet-50 text-violet-800"}`}>{message}</p>}{credentials && <div className="sm:col-span-2 space-y-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-xs font-semibold text-emerald-900">Employee login credentials</p><Credential label="Employee/login ID" value={credentials.loginId} copied={copied === "login"} onCopy={() => void copyCredential("login")} /><Credential label="Temporary password" value={credentials.password} copied={copied === "password"} onCopy={() => void copyCredential("password")} /><p className="text-[11px] text-emerald-800">The employee must change this temporary password on first login.</p></div>}{!credentials && <button type="submit" className="sm:col-span-2 rounded-xl bg-[#17191f] py-3 text-xs font-semibold text-white">Create employee</button>}</form></Modal>
    <Modal open={detailOpen} onClose={() => { setDetailOpen(false); setSelectedPerson(null); setDetailMessage(""); }} title={selectedPerson?.name ?? "Employee details"} description="Detailed employee profile from Aurora HR.">
      {selectedPerson && <form onSubmit={update} className="space-y-3 text-sm text-[#515763]"><div className="rounded-2xl bg-violet-50 p-4"><p className="text-xs uppercase tracking-[.2em] text-violet-600">Profile</p><p className="mt-2 font-semibold text-[#17191f]">{selectedPerson.title} - {selectedPerson.department}</p></div>{user.role === "admin" ? <div className="grid gap-3 sm:grid-cols-2"><FormField name="name" label="Full name" defaultValue={selectedPerson.name} /><FormField name="email" label="Email" type="email" defaultValue={selectedPerson.email} /><FormField name="phone" label="Phone" defaultValue={selectedPerson.phone} /><FormField name="department" label="Department" defaultValue={selectedPerson.department} /><FormField name="title" label="Job title" defaultValue={selectedPerson.title} /><FormField name="salary" label="Monthly salary" type="number" defaultValue={String(selectedPerson.salary)} /><FormField name="joining_date" label="Joining date" type="date" defaultValue={selectedPerson.joining_date} /><div className="flex items-end gap-2"><button type="submit" className="flex-1 rounded-xl bg-[#17191f] py-3 text-xs font-semibold text-white">Save changes</button><button type="button" onClick={deactivate} disabled={selectedPerson.status === "inactive"} className="rounded-xl border border-rose-200 px-3 py-3 text-xs font-semibold text-rose-700 disabled:opacity-40">Deactivate</button></div></div> : <div className="grid gap-3 sm:grid-cols-2"><Detail label="Employee code" value={selectedPerson.employee_code} /><Detail label="Email" value={selectedPerson.email} /><Detail label="Phone" value={selectedPerson.phone} /><Detail label="Location" value={selectedPerson.location} /><Detail label="Joining date" value={selectedPerson.joining_date} /><Detail label="Salary" value={`INR ${selectedPerson.salary.toLocaleString("en-IN")}`} /></div>}{detailMessage && <p className="rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{detailMessage}</p>}</form>}
    </Modal>
  </div>;
}

function FormField({ name, label, type = "text", defaultValue }: { name: string; label: string; type?: string; defaultValue?: string }) { return <label><span className="mb-1 block text-xs">{label}</span><input required name={name} type={type} defaultValue={defaultValue} className="w-full rounded-xl border border-black/[.09] bg-white p-3 text-sm" /></label>; }
function Detail({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">{label}</p><p className="mt-1 font-semibold">{value}</p></div>; }
function Credential({ label, value, copied, onCopy }: { label: string; value: string; copied: boolean; onCopy: () => void }) { return <div><p className="mb-1 text-[10px] font-medium text-emerald-800">{label}</p><div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-white p-2"><span className="mono min-w-0 flex-1 truncate text-xs font-semibold text-[#17191f]">{value}</span><button type="button" onClick={onCopy} title={`Copy ${label}`} aria-label={`Copy ${label}`} className="grid size-7 shrink-0 place-items-center rounded-md text-emerald-700 hover:bg-emerald-100">{copied ? <Check size={14} /> : <Copy size={14} />}</button></div></div>; }
