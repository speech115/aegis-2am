import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Aegis 2AM — Autonomous Banking Immune System",
  description:
    "Real-Time Client Shield + Self-Healing Bank powered by Graphify AST & Daytona Dual-Sandbox",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} dark`}>
      <body className="bg-[#07090E] text-[#E6EDF3] antialiased selection:bg-cyan-500/30">
        {children}
      </body>
    </html>
  );
}
