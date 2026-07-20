"use client";

import Image from "next/image";
import {
  useCallback,
  useEffect,
  useState,
} from "react";
import { useDropzone } from "react-dropzone";
import { FaCloudUploadAlt } from "react-icons/fa";

import AnalysisResultPanel from "@/components/upload/AnalysisResultPanel";
import { useUpload } from "@/hooks/useUpload";
import type { AnalysisRequest } from "@/types/analysis";

export default function UploadZone() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [pair, setPair] = useState<AnalysisRequest["pair"]>("GBPUSD");
  const [timeframe, setTimeframe] = useState<AnalysisRequest["timeframe"]>("M15");
  const [chartDatetime, setChartDatetime] = useState("");
  const [marketUtcOffsetHours, setMarketUtcOffsetHours] = useState(0);

  const {
    upload,
    loading,
    result,
    error,
    reset,
  } = useUpload();

  useEffect(() => {
    return () => {
      if (preview) {
        URL.revokeObjectURL(preview);
      }
    };
  }, [preview]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (!acceptedFiles.length) return;

    const image = acceptedFiles[0];
    setFile(image);
    setPreview(URL.createObjectURL(image));
    setClientError(null);
    reset();
  }, [reset]);

  const handleUpload = async () => {
    if (!file) {
      setClientError("Pilih gambar terlebih dahulu.");
      return;
    }

    if (!chartDatetime) {
      setClientError(
        "Isi waktu candle terakhir pada screenshot agar harga dapat dipetakan ke OHLCV.",
      );
      return;
    }

    setClientError(null);
    await upload({
      file,
      pair,
      timeframe,
      chartDatetime,
      marketUtcOffsetHours,
      confidenceThreshold: 0.25,
      chartCandles: 100,
      contextCandles: 300,
    });
  };

  const clearFile = () => {
    setFile(null);
    setPreview("");
    setClientError(null);
    reset();
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected: () => {
      setClientError(
        "Gunakan PNG, JPG, atau WEBP dengan ukuran maksimal 10 MB.",
      );
    },
    multiple: false,
    maxSize: 10 * 1024 * 1024,
    accept: {
      "image/png": [],
      "image/jpeg": [],
      "image/webp": [],
    },
  });

  if (file) {
    return (
      <div>
        <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-6 md:p-8">
          <div className="relative overflow-hidden rounded-2xl bg-black">
            <Image
              src={preview}
              alt="Preview chart yang akan dianalisis"
              width={1400}
              height={800}
              unoptimized
              className="mx-auto h-auto max-h-[520px] w-auto max-w-full object-contain"
            />
          </div>

          <div className="mt-6 flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="truncate font-medium text-white">{file.name}</p>
              <p className="text-sm text-neutral-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              type="button"
              onClick={clearFile}
              disabled={loading}
              className="rounded-xl border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800 disabled:opacity-50"
            >
              Ganti gambar
            </button>
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div>
              <label
                htmlFor="market-pair"
                className="mb-2 block text-sm text-neutral-400"
              >
                Market Pair
              </label>
              <select
                id="market-pair"
                value={pair}
                onChange={(event) => (
                  setPair(event.target.value as AnalysisRequest["pair"])
                )}
                className="w-full rounded-xl border border-neutral-700 bg-neutral-800 p-3 text-white outline-none focus:border-emerald-500"
              >
                <option value="GBPUSD">GBPUSD — Primary</option>
                <option value="XAUUSD">XAUUSD — Research</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="timeframe"
                className="mb-2 block text-sm text-neutral-400"
              >
                Timeframe
              </label>
              <select
                id="timeframe"
                value={timeframe}
                onChange={(event) => (
                  setTimeframe(
                    event.target.value as AnalysisRequest["timeframe"],
                  )
                )}
                className="w-full rounded-xl border border-neutral-700 bg-neutral-800 p-3 text-white outline-none focus:border-emerald-500"
              >
                <option value="M5">M5</option>
                <option value="M15">M15</option>
                <option value="H1">H1</option>
                <option value="H4">H4</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="chart-datetime"
                className="mb-2 block text-sm text-neutral-400"
              >
                Waktu candle terakhir
              </label>
              <input
                id="chart-datetime"
                type="datetime-local"
                value={chartDatetime}
                onChange={(event) => setChartDatetime(event.target.value)}
                required
                className="w-full rounded-xl border border-neutral-700 bg-neutral-800 p-3 text-white outline-none focus:border-emerald-500"
              />
              <p className="mt-2 text-xs text-neutral-500">
                Gunakan waktu yang terlihat pada chart, bukan waktu upload.
              </p>
            </div>

            <div>
              <label
                htmlFor="utc-offset"
                className="mb-2 block text-sm text-neutral-400"
              >
                UTC offset waktu chart
              </label>
              <input
                id="utc-offset"
                type="number"
                min={-12}
                max={14}
                step={0.5}
                value={marketUtcOffsetHours}
                onChange={(event) => (
                  setMarketUtcOffsetHours(Number(event.target.value))
                )}
                className="w-full rounded-xl border border-neutral-700 bg-neutral-800 p-3 text-white outline-none focus:border-emerald-500"
              />
              <p className="mt-2 text-xs text-neutral-500">
                Contoh: UTC+0 diisi 0, UTC+2 diisi 2.
              </p>
            </div>
          </div>

          {(clientError || error) && (
            <div className="mt-6 rounded-xl border border-red-900/70 bg-red-950/40 p-4 text-sm text-red-200">
              {clientError ?? error}
            </div>
          )}

          <button
            type="button"
            onClick={handleUpload}
            disabled={loading || !chartDatetime}
            className="mt-8 w-full rounded-xl bg-emerald-500 py-3 font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading
              ? "Menjalankan CNN, YOLO, dan OHLCV..."
              : "Analisis Chart"}
          </button>

          <p className="mt-3 text-center text-xs text-neutral-500">
            AI-TDSS adalah decision support system dan tidak mengeksekusi transaksi.
          </p>
        </div>

        {result && <AnalysisResultPanel result={result} />}
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`cursor-pointer rounded-3xl border-2 border-dashed px-6 py-20 transition md:p-24 ${
        isDragActive
          ? "border-emerald-500 bg-neutral-800"
          : "border-neutral-700 bg-neutral-900"
      }`}
    >
      <input {...getInputProps()} />

      <div className="flex flex-col items-center">
        <FaCloudUploadAlt size={70} className="mb-8 text-neutral-400" />
        <h2 className="text-3xl font-bold text-white">
          Drag & Drop Chart
        </h2>
        <p className="mt-4 text-neutral-400">
          atau klik untuk memilih screenshot
        </p>
        <p className="mt-8 text-sm text-neutral-500">
          PNG • JPG • JPEG • WEBP
        </p>
        <p className="text-sm text-neutral-500">Maksimal 10 MB</p>

        {(clientError || error) && (
          <p className="mt-5 max-w-lg text-center text-sm text-red-300">
            {clientError ?? error}
          </p>
        )}
      </div>
    </div>
  );
}
