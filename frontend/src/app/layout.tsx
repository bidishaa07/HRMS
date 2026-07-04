import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aurora HR — Autonomous Workforce OS",
  description: "Enterprise human resources, orchestrated by a private AI workforce.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

