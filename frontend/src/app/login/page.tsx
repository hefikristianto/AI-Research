"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { Eye, EyeOff } from "lucide-react";
import { login } from "@/services/auth.service";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    setLoading(true);
    setError("");

    try {
      const res = await login({ email, password });

      Cookies.set("access_token", res.session.access_token, { path: "/" });
      Cookies.set("refresh_token", res.session.refresh_token, { path: "/" });

      router.push("/dashboard");
    } catch (err: unknown) {
      const error = err as {
        response?: {
          data?: {
            detail?: string;
          };
        };
      };

      setError(typeof error.response?.data?.detail === "string" ? error.response.data.detail : JSON.stringify(error.response?.data?.detail || "Login gagal"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-neutral-950 text-white">
      <form
        onSubmit={handleLogin}
        className="w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-900 p-8 space-y-5"
      >
        <div>
          <h1 className="text-2xl font-bold">Login AI-TDSS</h1>
          <p className="text-sm text-neutral-400 mt-2">
            AI Trading Decision Support System
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500 bg-red-500/10 p-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
        />

        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 pr-12"
          />

          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-white"
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        </div>

        <button
          disabled={loading}
          className="w-full rounded-lg bg-white py-3 font-semibold text-black"
        >
          {loading ? "Loading..." : "Login"}
        </button>

        <p className="text-center text-sm text-neutral-400">
          Belum punya akun?{" "}
          <a href="/register" className="text-white underline">
            Register
          </a>
        </p>
      </form>
    </main>
  );
}
