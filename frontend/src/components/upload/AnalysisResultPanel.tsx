import Image from "next/image";

import type {
  FullAnalysisResult,
  PublicDecision,
} from "@/types/analysis";

const DECISION_STYLE: Record<PublicDecision, string> = {
  BUY: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  SELL: "border-red-500/40 bg-red-500/10 text-red-300",
  WATCHLIST: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  NO_TRADE: "border-neutral-700 bg-neutral-800 text-neutral-200",
};

const REASON_TEXT: Record<string, string> = {
  ALL_EXECUTION_GATES_PASSED: (
    "Semua quality, structure, session, dan risk gate telah lolos."
  ),
  NO_VALID_SETUP: (
    "Belum ada pasangan zona OB/FVG yang memenuhi syarat setup."
  ),
  NO_TRADE_DECISION: (
    "Bukti yang tersedia belum mendukung entry baru."
  ),
  EXECUTION_REVIEW_REQUIRED: (
    "Setup perlu konfirmasi tambahan sebelum dapat menjadi entry."
  ),
  DETECTOR_CONFIDENCE_INVALID: (
    "Confidence zona visual belum memenuhi ambang detector."
  ),
  RISK_REWARD_UNAVAILABLE: (
    "Entry, stop loss, dan target belum dapat dihitung secara aman."
  ),
  RISK_REWARD_BELOW_1_5: (
    "Risk-reward berada di bawah batas minimum 1.5R."
  ),
  ENTRY_SIDE_INVALID: (
    "Posisi entry tidak konsisten dengan arah setup dan harga saat ini."
  ),
  ZONE_INVALIDATED: (
    "Pergerakan harga telah membatalkan zona kandidat."
  ),
  ADVANCED_SCORE_BELOW_WATCHLIST: (
    "Skor gabungan belum cukup bahkan untuk status watchlist."
  ),
  STRUCTURE_AND_HTF_CONFLICT: (
    "Arah struktur market berkonflik dengan higher timeframe."
  ),
  PRICE_MAPPING_PROVISIONAL: (
    "Pemetaan pixel chart ke harga masih bersifat provisional."
  ),
  LOW_MAPPING_CONFIDENCE: (
    "Confidence pemetaan pixel ke harga masih terlalu rendah."
  ),
  LOW_SESSION_SUITABILITY: (
    "Waktu chart berada pada sesi dengan kecocokan yang lebih rendah."
  ),
  EXTREME_VOLATILITY: (
    "Volatilitas ekstrem membuat risiko entry terlalu tinggi."
  ),
  ENTRY_DISTANCE_EXCEEDS_3_ATR: (
    "Harga sudah lebih dari 3 ATR dari kandidat entry."
  ),
  ENTRY_DISTANCE_ABOVE_1_5_ATR: (
    "Harga sudah lebih dari 1.5 ATR dari kandidat entry."
  ),
};

function formatNumber(
  value: number | null,
  maximumFractionDigits = 5,
) {
  if (value === null || !Number.isFinite(value)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
  }).format(value);
}

function humanize(value: string) {
  if (!value.includes("_")) {
    return value;
  }

  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (character) => character.toUpperCase());
}

type AnalysisResultPanelProps = {
  result: FullAnalysisResult;
};

export default function AnalysisResultPanel({
  result,
}: AnalysisResultPanelProps) {
  const recommendation = result.recommendation;
  const probabilities = result.regime.probabilities ?? {};
  const classCounts = result.detection.class_counts ?? {};
  const metricCards = [
    {
      label: "Entry",
      value: recommendation.entry,
      digits: 5,
    },
    {
      label: "Stop Loss",
      value: recommendation.stop_loss,
      digits: 5,
    },
    {
      label: "Take Profit",
      value: recommendation.take_profit,
      digits: 5,
    },
    {
      label: "Risk / Reward",
      value: recommendation.risk_reward_ratio,
      digits: 2,
    },
  ];
  const explanationGroups = [
    {
      title: "Blockers",
      items: recommendation.blockers,
      color: "text-red-300",
    },
    {
      title: "Warnings",
      items: recommendation.warnings,
      color: "text-amber-300",
    },
    {
      title: "Reasons",
      items: recommendation.reasons,
      color: "text-sky-300",
    },
  ].filter((group) => group.items.length > 0);

  return (
    <section className="mt-8 space-y-6">
      <div
        className={`rounded-2xl border p-6 ${DECISION_STYLE[recommendation.decision]}`}
      >
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] opacity-70">
              AI-TDSS Recommendation
            </p>
            <h2 className="mt-2 text-4xl font-black">
              {recommendation.decision.replace("_", " ")}
            </h2>
          </div>

          <div className="text-left md:text-right">
            <p className="text-sm opacity-70">Execution status</p>
            <p className="mt-1 font-semibold">
              {humanize(recommendation.execution_status)}
            </p>
          </div>
        </div>

        <p className="mt-4 text-sm opacity-80">
          {recommendation.actionable
            ? "Seluruh execution gate telah lolos. Tetap lakukan verifikasi mandiri sebelum mengambil keputusan."
            : "Hasil ini bersifat edukatif dan belum merupakan entry yang siap dieksekusi."}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((card) => (
          <div
            key={card.label}
            className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5"
          >
            <p className="text-sm text-neutral-500">{card.label}</p>
            <p className="mt-2 text-2xl font-bold text-white">
              {formatNumber(card.value, card.digits)}
            </p>
          </div>
        ))}
      </div>

      {result.annotated_chart.status === "RENDERED"
        && result.annotated_chart.data_url ? (
          <div className="overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900">
            <div className="flex items-center justify-between border-b border-neutral-800 px-5 py-4">
              <div>
                <h3 className="font-semibold text-white">
                  Annotated Chart
                </h3>
                <p className="text-sm text-neutral-500">
                  {result.annotated_chart.rendered_detections} zona OB/FVG divisualisasikan
                </p>
              </div>

              <div className="hidden gap-3 text-xs text-neutral-400 sm:flex">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-sky-500" />
                  Order Block
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-purple-500" />
                  Fair Value Gap
                </span>
              </div>
            </div>

            <div className="p-4">
              <Image
                src={result.annotated_chart.data_url}
                alt="Chart dengan bounding box hasil analisis AI-TDSS"
                width={result.annotated_chart.width ?? result.width}
                height={result.annotated_chart.height ?? result.height}
                unoptimized
                className="h-auto w-full rounded-xl"
              />
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-red-900/60 bg-red-950/30 p-5 text-sm text-red-200">
            Annotated chart belum tersedia: {result.annotated_chart.error ?? "rendering tidak selesai"}
          </div>
        )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
          <h3 className="font-semibold text-white">Market Regime</h3>
          <p className="mt-2 text-2xl font-bold capitalize text-white">
            {result.regime.label ?? "unknown"}
          </p>
          <p className="text-sm text-neutral-500">
            Confidence {formatNumber((result.regime.confidence ?? 0) * 100, 1)}%
          </p>

          <div className="mt-5 space-y-3">
            {Object.entries(probabilities).map(([
              label,
              probability,
            ]) => (
              <div key={label}>
                <div className="mb-1 flex justify-between text-xs capitalize text-neutral-400">
                  <span>{label}</span>
                  <span>{formatNumber(probability * 100, 1)}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-neutral-800">
                  <div
                    className="h-full rounded-full bg-sky-500"
                    style={{
                      width: `${Math.max(0, Math.min(100, probability * 100))}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
          <h3 className="font-semibold text-white">Detection Summary</h3>
          <p className="mt-2 text-2xl font-bold text-white">
            {result.detection.total ?? 0} detections
          </p>

          <div className="mt-5 space-y-3">
            {Object.entries(classCounts).length > 0 ? (
              Object.entries(classCounts).map(([
                className,
                count,
              ]) => (
                <div
                  key={className}
                  className="flex items-center justify-between rounded-xl bg-neutral-800/70 px-4 py-3"
                >
                  <span className="text-sm text-neutral-300">
                    {humanize(className)}
                  </span>
                  <span className="font-semibold text-white">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-neutral-500">
                Tidak ada zona OB/FVG yang melewati threshold.
              </p>
            )}
          </div>
        </div>
      </div>

      {explanationGroups.length > 0 && (
        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
          <h3 className="font-semibold text-white">
            Why this recommendation?
          </h3>

          <div className="mt-5 grid gap-5 md:grid-cols-3">
            {explanationGroups.map((group) => (
              <div key={group.title}>
                <p className={`text-sm font-semibold ${group.color}`}>
                  {group.title}
                </p>
                <ul className="mt-2 space-y-2 text-sm text-neutral-300">
                  {group.items.map((item) => (
                    <li key={item} className="leading-relaxed">
                      <span>• {REASON_TEXT[item] ?? humanize(item)}</span>
                      {REASON_TEXT[item] && (
                        <code className="mt-1 block text-[10px] text-neutral-600">
                          {item}
                        </code>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-neutral-800 bg-neutral-950 px-4 py-3 text-xs text-neutral-500">
        <span className="font-semibold text-neutral-400">Pipeline:</span>{" "}
        {humanize(result.pipeline_status)} · {result.metadata.pair ?? "Unknown pair"} · {result.metadata.timeframe ?? "Unknown timeframe"}
      </div>
    </section>
  );
}
