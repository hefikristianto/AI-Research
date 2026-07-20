import api from "@/lib/axios";
import type {
  AnalysisRequest,
  FullAnalysisResult,
} from "@/types/analysis";

export async function analyzeChart(
  request: AnalysisRequest,
) {
  const formData = new FormData();
  formData.append(
    "file",
    request.file,
    request.file.name,
  );

  const { data } = await api.post<FullAnalysisResult>(
    "/api/analysis/full",
    formData,
    {
      params: {
        pair: request.pair,
        timeframe: request.timeframe,
        chart_datetime: request.chartDatetime,
        market_utc_offset_hours: request.marketUtcOffsetHours,
        confidence_threshold: request.confidenceThreshold ?? 0.25,
        chart_candles: request.chartCandles ?? 100,
        context_candles: request.contextCandles ?? 300,
      },
    },
  );

  return data;
}
