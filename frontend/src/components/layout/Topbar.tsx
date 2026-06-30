type TopbarProps = {
  userName?: string;
};

export default function Topbar({ userName = "User" }: TopbarProps) {
  return (
    <header className="h-16 border-b border-neutral-800 bg-neutral-950 px-8 flex items-center justify-between text-white">
      <div>
        <h2 className="font-semibold">Dashboard</h2>
        <p className="text-xs text-neutral-500">
          AI Trading Decision Support System
        </p>
      </div>

      <div className="text-sm text-neutral-300">
        {userName}
      </div>
    </header>
  );
}
