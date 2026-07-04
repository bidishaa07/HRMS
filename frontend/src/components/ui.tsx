import type { ReactNode } from "react";
import { clsx } from "clsx";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={clsx("glass rounded-[24px]", className)}>{children}</section>;
}

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "green" | "amber" | "violet" }) {
  const styles = { neutral: "bg-black/[.045] text-[#68707d]", green: "bg-emerald-100 text-emerald-700", amber: "bg-amber-100 text-amber-700", violet: "bg-violet-100 text-violet-700" };
  return <span className={clsx("inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold", styles[tone])}>{children}</span>;
}

