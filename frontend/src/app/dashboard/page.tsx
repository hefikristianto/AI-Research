"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { getMe } from "@/services/auth.service";

export default function DashboardPage() {
  const router = useRouter();

  const [name, setName] = useState("User");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = Cookies.get("access_token");

    if (!token) {
      router.push("/login");
      return;
    }

    const loadProfile = async () => {
      try {
        const res = await getMe();

        setName(res.profile?.full_name || res.user?.email || "User");
      } catch {
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        router.push("/login");
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [router]);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-neutral-950 text-white">
        Loading dashboard...
      </main>
    );
  }

  return (
    <DashboardLayout userName={name}>
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Welcome Back, {name}</h1>
          <p className="text-neutral-400 mt-2">
            Pantau analisis chart, watchlist, dan journal trading dari satu tempat.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
            <p className="text-sm text-neutral-400">Total Analysis</p>
            <h2 className="text-3xl font-bold mt-3">0</h2>
          </div>

          <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
            <p className="text-sm text-neutral-400">Active Watchlist</p>
            <h2 className="text-3xl font-bold mt-3">0</h2>
          </div>

          <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
            <p className="text-sm text-neutral-400">Winrate</p>
            <h2 className="text-3xl font-bold mt-3">0%</h2>
          </div>

          <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
            <p className="text-sm text-neutral-400">Journal</p>
            <h2 className="text-3xl font-bold mt-3">0</h2>
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
          <h2 className="text-xl font-semibold">Recent Analysis</h2>
          <p className="text-neutral-500 mt-2">
            Belum ada analisis. Tenang, AI juga butuh gambar dulu sebelum sok pintar.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
