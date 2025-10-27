import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PRL Notifier",
  description:
    "PWA para gestionar cargas de ficheros y notificaciones preventivas dentro del roadmap Semana 1.",
  manifest: "/manifest.json"
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full">
      <body className={`${inter.className} h-full bg-slate-50`}>{children}</body>
    </html>
  );
}
