"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";

export function Modal({ title, description, open, onClose, children }: { title: string; description?: string; open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-[#101116]/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
    <section className="max-h-[92vh] w-full max-w-lg overflow-auto rounded-[24px] bg-[#f9fafb] p-6 shadow-2xl">
      <div className="mb-5 flex items-start justify-between"><div><h2 id="modal-title" className="text-lg font-semibold tracking-tight">{title}</h2>{description && <p className="mt-1 text-xs text-[#858c97]">{description}</p>}</div><button onClick={onClose} className="grid size-8 place-items-center rounded-lg bg-black/[.04]" aria-label="Close dialog"><X size={15} /></button></div>
      {children}
    </section>
  </div>;
}

