import Link from "next/link";
import {
  LayoutDashboard,
  Upload,
  BarChart3,
  BookOpen,
  Eye,
  Settings,
  LogOut
} from "lucide-react";
import Cookies from "js-cookie";

export default function Sidebar() {
  const menus = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Upload", href: "/upload", icon: Upload },
    { name: "Analysis", href: "/analysis", icon: BarChart3 },
    { name: "Journal", href: "/journal", icon: BookOpen },
    { name: "Watchlist", href: "/watchlist", icon: Eye },
    { name: "Settings", href: "/settings", icon: Settings },
  ];

  const logout = () => {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    window.location.href = "/login";
  };

  return (
    <aside className="w-64 min-h-screen bg-neutral-950 border-r border-neutral-800 p-5 text-white">
      <div className="mb-10">
        <h1 className="text-xl font-bold">AI-TDSS</h1>
        <p className="text-xs text-neutral-500 mt-1">Trading Assistant</p>
      </div>

      <nav className="space-y-2">
        {menus.map((item) => {
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-neutral-300 hover:bg-neutral-900 hover:text-white"
            >
              <Icon size={18} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={logout}
        className="mt-10 flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-red-400 hover:bg-red-500/10"
      >
        <LogOut size={18} />
        Logout
      </button>
    </aside>
  );
}
