export type PublicDecision =
  | "BUY"
  | "SELL"
  | "WATCHLIST"
  | "NO_TRADE";

export type AnalysisRequest = {
  file: File;
  pair: "GBPUSD" | "XAUUSD";
  timeframe: "M5" | "M15" | "H1" | "H4";
  chartDatetime: string;
  marketUtcOffsetHours: number;
  confidenceThreshold?: number;
  chartCandles?: number;
  contextCandles?: number;
};

export type Recommendation = {
  decision: PublicDecision;
  internal_decision: string;
  execution_status: string;
  final_decision_ready: boolean;
  actionable: boolean;
  educational_only: boolean;
  entry: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward_ratio: number | null;
  order_type: string | null;
  setup_direction: string;
  blockers: string[];
  warnings: string[];
  reasons: string[];
};

export type AnnotatedChart = {
  status: string;
  media_type?: string;
  encoding?: string;
  data_url?: string;
  sha256?: string;
  width?: number;
  height?: number;
  rendered_detections: number;
  error?: string;
};

export type RegimeResult = {
  label?: string;
  confidence?: number;
  probabilities?: Record<string, number>;
  device?: string;
  [key: string]: unknown;
};

export type DetectionResult = {
  total?: number;
  class_counts?: Record<string, number>;
  confidence_threshold?: number;
  detections?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

export type FullAnalysisResult = {
  filename: string;
  content_type: string;
  width: number;
  height: number;
  metadata: {
    pair?: string | null;
    timeframe?: string | null;
    chart_datetime?: string | null;
    metadata_source?: string;
    [key: string]: unknown;
  };
  regime: RegimeResult;
  detection: DetectionResult;
  pairing: Record<string, unknown>;
  scoring: Record<string, unknown>;
  ohlcv_context: Record<string, unknown>;
  market_structure: Record<string, unknown>;
  context_scoring: Record<string, unknown>;
  htf_volatility: Record<string, unknown>;
  advanced_scoring: Record<string, unknown>;
  price_conversion: Record<string, unknown>;
  session_risk: Record<string, unknown>;
  execution_gate: Record<string, unknown>;
  recommendation: Recommendation;
  annotated_chart: AnnotatedChart;
  pipeline_status: string;
};
