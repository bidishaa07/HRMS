"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FileText, Loader2, UploadCloud } from "lucide-react";
import { api, ApiError, type DocumentItem } from "@/lib/api";
import { Modal } from "../modal";
import { Card, Pill } from "../ui";

export function DocumentsView() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<DocumentItem | null>(null);

  async function load() { setLoading(true); try { setDocuments(await api.documents()); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, []);
  async function upload(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); setMessage(""); try { await api.uploadDocument(form); setMessage("Document uploaded successfully."); event.currentTarget.reset(); await load(); } catch (reason) { setMessage(reason instanceof ApiError ? reason.message : "Upload failed"); } }

  return <div className="space-y-5"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">Knowledge base</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Documents</h2><p className="mt-1 text-xs text-[#858c97]">Secure employee files and AI-searchable HR policies.</p></div><Card className="p-5"><form onSubmit={upload} className="flex flex-col gap-3 sm:flex-row sm:items-end"><label className="flex-1 text-xs">Choose document<input required name="file" type="file" className="mt-1 block w-full rounded-xl border border-dashed border-violet-200 bg-violet-50/50 p-3 text-xs" /></label><label className="text-xs">Type<select name="document_type" className="mt-1 block w-full rounded-xl border border-black/[.09] bg-white p-3"><option>Resume</option><option>Certificate</option><option>HR Policy</option><option>Contract</option><option>Other</option></select></label><button className="flex items-center justify-center gap-2 rounded-xl bg-[#17191f] px-5 py-3 text-xs font-semibold text-white"><UploadCloud size={14} />Upload</button></form>{message && <p className="mt-3 rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{message}</p>}</Card><Card className="p-5"><h3 className="text-sm font-semibold">Document library</h3>{loading ? <div className="grid h-32 place-items-center"><Loader2 className="animate-spin text-violet-600" /></div> : <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{documents.map((document) => <button key={document.id} type="button" onClick={() => setSelectedDocument(document)} className="text-left"><article className="flex items-center gap-3 rounded-xl border border-black/[.06] bg-white/60 p-3"><div className="grid size-9 place-items-center rounded-xl bg-violet-100 text-violet-700"><FileText size={16} /></div><div className="min-w-0"><p className="truncate text-xs font-medium">{document.name}</p><div className="mt-1"><Pill tone="violet">{document.document_type}</Pill></div></div></article></button>)}{documents.length === 0 && <p className="text-xs text-[#9298a1]">No documents uploaded yet.</p>}</div>}</Card><Modal open={Boolean(selectedDocument)} onClose={() => setSelectedDocument(null)} title={selectedDocument?.name ?? "Document details"} description="Secure file details and download access.">{selectedDocument && <div className="space-y-3 text-sm text-[#515763]"><div className="rounded-2xl bg-violet-50 p-4"><p className="text-xs uppercase tracking-[.2em] text-violet-600">Document type</p><p className="mt-2 font-semibold text-[#17191f]">{selectedDocument.document_type}</p></div><button onClick={() => window.open(api.documentDownloadUrl(selectedDocument.id), "_blank", "noopener,noreferrer")} className="w-full rounded-xl bg-[#17191f] px-4 py-3 text-xs font-semibold text-white">Download file</button></div>}</Modal></div>;
}
