"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { FaCloudUploadAlt } from "react-icons/fa";
import { useUpload } from "@/hooks/useUpload";

export default function UploadZone() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");

  const [pair, setPair] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [session, setSession] = useState("london");
  const [device, setDevice] = useState("desktop");

  const { upload, loading } = useUpload();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (!acceptedFiles.length) return;

    const image = acceptedFiles[0];

    setFile(image);
    setPreview(URL.createObjectURL(image));
  }, []);

  const handleUpload = async () => {
    if (!file) {
      alert("Pilih gambar terlebih dahulu.");
      return;
    }

    const formData = new FormData();

    formData.append("image", file);
    formData.append("pair", pair);
    formData.append("timeframe", timeframe);
    formData.append("device", device);
    formData.append("market_session", session);

    try {
      const result = await upload(formData);

      console.log("Upload success:", result);

      alert("Upload berhasil");
    } catch (error) {
      console.error("Upload failed:", error);

      alert("Upload gagal");
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      "image/png": [],
      "image/jpeg": [],
      "image/webp": [],
    },
  });

  if (file) {
    return (
      <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-8">
        <img
          src={preview}
          alt="Preview"
          className="mx-auto max-h-[450px] rounded-xl"
        />

        <div className="mt-8 grid grid-cols-2 gap-6">
          <div>
            <label className="mb-2 block text-sm text-neutral-400">
              Market Pair
            </label>

            <select
              value={pair}
              onChange={(e) => setPair(e.target.value)}
              className="w-full rounded-xl bg-neutral-800 p-3"
            >
              <option value="EURUSD">EURUSD</option>
              <option value="GBPUSD">GBPUSD</option>
              <option value="XAUUSD">XAUUSD</option>
              <option value="BTCUSD">BTCUSD</option>
            </select>
          </div>

          <div>
            <label className="mb-2 block text-sm text-neutral-400">
              Timeframe
            </label>

            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="w-full rounded-xl bg-neutral-800 p-3"
            >
              <option value="M1">M1</option>
              <option value="M5">M5</option>
              <option value="M15">M15</option>
              <option value="M30">M30</option>
              <option value="H1">H1</option>
              <option value="H4">H4</option>
              <option value="D1">D1</option>
            </select>
          </div>

          <div>
            <label className="mb-2 block text-sm text-neutral-400">
              Session
            </label>

            <select
              value={session}
              onChange={(e) => setSession(e.target.value)}
              className="w-full rounded-xl bg-neutral-800 p-3"
            >
              <option value="asia">Asia</option>
              <option value="london">London</option>
              <option value="newyork">New York</option>
              <option value="overlap">Overlap</option>
            </select>
          </div>

          <div>
            <label className="mb-2 block text-sm text-neutral-400">
              Device
            </label>

            <select
              value={device}
              onChange={(e) => setDevice(e.target.value)}
              className="w-full rounded-xl bg-neutral-800 p-3"
            >
              <option value="desktop">Desktop</option>
              <option value="mobile">Mobile</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleUpload}
          disabled={loading}
          className="mt-8 w-full rounded-xl bg-emerald-500 py-3 font-semibold text-black hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Uploading..." : "Upload Chart"}
        </button>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`cursor-pointer rounded-3xl border-2 border-dashed p-24 transition ${
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

        <p className="text-sm text-neutral-500">
          Maksimal 10 MB
        </p>
      </div>
    </div>
  );
}
