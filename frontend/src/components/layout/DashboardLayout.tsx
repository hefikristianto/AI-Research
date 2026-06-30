"use client";

import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

type DashboardLayoutProps = {
  children: React.ReactNode;
  userName?: string;
};

export default function DashboardLayout({
  children,
  userName = "User",
}: DashboardLayoutProps) {
  return (
    <main className="min-h-screen bg-neutral-950 text-white flex">
      <Sidebar />

      <section className="flex-1">
        <Topbar userName={userName} />
        <div className="p-8">
          {children}
        </div>
      </section>
    </main>
  );
}
