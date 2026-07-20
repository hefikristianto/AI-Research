"use client";

import axios from "axios";
import { useCallback, useState } from "react";

import { analyzeChart } from "@/services/upload";
import type {
  AnalysisRequest,
  FullAnalysisResult,
} from "@/types/analysis";

function resolveErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const responseData = error.response?.data as
      | { detail?: unknown }
      | undefined;

    if (typeof responseData?.detail === "string") {
      return responseData.detail;
    }

    if (error.code === "ERR_NETWORK") {
      return (
        "Backend tidak dapat dihubungi. "
        + "Pastikan FastAPI berjalan di port 8000."
      );
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Analisis gagal karena error yang tidak dikenal.";
}

export function useUpload() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FullAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = async (request: AnalysisRequest) => {
    try {
      setLoading(true);
      setError(null);
      const analysis = await analyzeChart(request);
      setResult(analysis);
      return analysis;
    } catch (caughtError) {
      setResult(null);
      setError(resolveErrorMessage(caughtError));
      return null;
    } finally {
      setLoading(false);
    }
  };

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return {
    upload,
    loading,
    result,
    error,
    reset,
  };
}
