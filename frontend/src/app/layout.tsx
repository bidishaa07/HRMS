import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/query-provider";

export const metadata: Metadata = {
  title: "Aurora HR — Autonomous Workforce OS",
  description: "Enterprise human resources, orchestrated by a private AI workforce.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><QueryProvider>{children}</QueryProvider></body>
    </html>
  );
}
