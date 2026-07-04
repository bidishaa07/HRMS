"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Mail, MapPin, Plus, Search, ShieldCheck } from "lucide-react";
import { api, ApiError, type Employee, type User } from "@/lib/api";
import { Modal } from "../modal";
import { Card, Pill } from "../ui";

export function PeopleView({ user }: { user: User }) {
  const [people, setPeople] = useState<Employee[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedPerson, setSelectedPerson] = useState<Employee | null>(null);
  const [message, setMessage] = useState("");

  async function load(query = search) {
    setLoading(true);
    try { setPeople(await api.employees(query)); } finally { setLoading(false); }
  }
  useEffect(() => { setLoading(true); api.employees("").then(setPeople).finally(() => setLoading(false)); }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await api.createEmployee({
        name: String(data.get("name")), email: String(data.get("email")), phone: String(data.get("phone")),
        department: String(data.get("department")), title: String(data.get("title")),
        salary: Number(data.get("salary")), joining_date: String(data.get("joining_date")),
      });
      setMessage(`Created ${result.employee_code}. Temporary password: ${result.temporary_password}`);
      event.currentTarget.reset(); await load("");
    } catch (reason) { setMessage(reason instanceof ApiError ? reason.message : "Could not create employee"); }
  }

  return <div className="space-y-5">
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">People directory</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Employees</h2><p className="mt-1 text-xs text-[#858c97]">Live status, role, department, and workforce health.</p></div>{user.role !== "employee" && <button onClick={() => setOpen(true)} className="flex items-center justify-center gap-2 rounded-xl bg-[#17191f] px-4 py-2.5 text-xs font-semibold text-white"><Plus size={14} />New employee</button>}</div>
    <Card className="p-4"><form onSubmit={(event) => { event.preventDefault(); void load(); }} className="flex items-center gap-2"><Search size={15} className="text-[#949aa4]" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm outline-none" placeholder="Search by name, email, or login ID" /><button className="rounded-lg bg-black/[.05] px-3 py-1.5 text-[10px] font-semibold">Search</button></form></Card>
    {loading ? <div className="grid h-48 place-items-center"><Loader2 className="animate-spin text-violet-600" /></div> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{people.map((person) => <button key={person.id} type="button" onClick={() => { setSelectedPerson(person); setDetailOpen(true); }} className="text-left"><Card className="p-5 transition hover:-translate-y-0.5 hover:shadow-xl"><div className="flex items-start justify-between"><div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-violet-100 to-pink-100 text-xs font-bold text-violet-700">{person.name.split(" ").map((part) => part[0]).slice(0,2).join("")}</div><span title={person.status} className={`size-2.5 rounded-full ${person.status === "present" ? "bg-emerald-500" : person.status === "late" ? "bg-amber-400" : person.status === "leave" ? "bg-blue-500" : "bg-rose-400"}`} /></div><h3 className="mt-4 text-sm font-semibold">{person.name}</h3><p className="mt-0.5 text-[10px] text-[#858c97]">{person.title} · {person.department}</p><div className="mt-4 space-y-2 border-t border-black/[.05] pt-4 text-[10px] text-[#737b87]"><p className="flex items-center gap-2"><ShieldCheck size={12} />{person.employee_code}</p><p className="flex items-center gap-2"><Mail size={12} />{person.email}</p><p className="flex items-center gap-2"><MapPin size={12} />{person.location}</p></div><div className="mt-4 flex items-center justify-between"><Pill tone={person.status === "present" ? "green" : person.status === "late" ? "amber" : "neutral"}>{person.status}</Pill><span className="mono text-[9px] text-[#878e99]">Health {person.health_score}/100</span></div></Card></button>)}</div>}
    <Modal open={open} onClose={() => { setOpen(false); setMessage(""); }} title="Add employee" description="Aurora generates the login ID and provisions a temporary password."><form onSubmit={create} className="grid gap-3 sm:grid-cols-2"><FormField name="name" label="Full name" /><FormField name="email" label="Email" type="email" /><FormField name="phone" label="Phone" /><FormField name="department" label="Department" /><FormField name="title" label="Job title" /><FormField name="salary" label="Monthly salary" type="number" /><label className="sm:col-span-2"><span className="mb-1 block text-xs">Joining date</span><input required name="joining_date" type="date" defaultValue={new Date().toISOString().slice(0,10)} className="w-full rounded-xl border border-black/[.09] bg-white p-3 text-sm" /></label>{message && <p className="sm:col-span-2 rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{message}</p>}<button className="sm:col-span-2 rounded-xl bg-[#17191f] py-3 text-xs font-semibold text-white">Create employee</button></form></Modal>
    <Modal open={detailOpen} onClose={() => { setDetailOpen(false); setSelectedPerson(null); }} title={selectedPerson?.name ?? "Employee details"} description="Detailed employee profile from Aurora HR.">
      {selectedPerson && <div className="space-y-3 text-sm text-[#515763]"><div className="rounded-2xl bg-violet-50 p-4"><p className="text-xs uppercase tracking-[.2em] text-violet-600">Profile</p><p className="mt-2 font-semibold text-[#17191f]">{selectedPerson.title} · {selectedPerson.department}</p></div><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">Employee code</p><p className="mt-1 font-semibold">{selectedPerson.employee_code}</p></div><div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">Email</p><p className="mt-1 font-semibold">{selectedPerson.email}</p></div><div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">Phone</p><p className="mt-1 font-semibold">{selectedPerson.phone}</p></div><div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">Location</p><p className="mt-1 font-semibold">{selectedPerson.location}</p></div><div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">Joining date</p><p className="mt-1 font-semibold">{selectedPerson.joining_date}</p></div><div className="rounded-2xl border border-black/[.05] p-3"><p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">Salary</p><p className="mt-1 font-semibold">₹{selectedPerson.salary.toLocaleString("en-IN")}</p></div></div></div>}
    </Modal>
  </div>;
}

function FormField({ name, label, type = "text" }: { name: string; label: string; type?: string }) { return <label><span className="mb-1 block text-xs">{label}</span><input required name={name} type={type} className="w-full rounded-xl border border-black/[.09] bg-white p-3 text-sm" /></label>; }
