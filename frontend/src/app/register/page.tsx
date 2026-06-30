"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { register } from "@/services/auth.service";

export default function RegisterPage() {
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRegister = async (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    setLoading(true);
    setError("");

    try {
      await register({
        full_name: fullName,
        email,
        password,
      });

      router.push("/login");
    } catch (err: unknown) {
      const error = err as {
        response?: {
          data?: {
            detail?: string;
          };
        };
      };

      setError(typeof error.response?.data?.detail === "string" ? error.response.data.detail : JSON.stringify(error.response?.data?.detail || "Register gagal"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-neutral-950 text-white">
      <form
        onSubmit={handleRegister}
        className="w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-900 p-8 space-y-5"
      >
        <div>
          <h1 className="text-2xl font-bold">Register AI-TDSS</h1>
          <p className="text-sm text-neutral-400 mt-2">
            Buat akun untuk mulai analisis chart.
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500 bg-red-500/10 p-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        <input
          type="text"
          placeholder="Full Name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
        />

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
          {loading ? "Loading..." : "Register"}
        </button>

        <p className="text-center text-sm text-neutral-400">
          Sudah punya akun?{" "}
          <a href="/login" className="text-white underline">
            Login
          </a>
        </p>
      </form>
    </main>
  );
}
