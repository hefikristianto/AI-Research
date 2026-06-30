"use client";

import { useState } from "react";
import { uploadChart } from "@/services/upload";

export function useUpload() {
  const [loading, setLoading] = useState(false);

  const upload = async (formData: FormData) => {
    try {
      setLoading(true);
      return await uploadChart(formData);
    } finally {
      setLoading(false);
    }
  };

  return {
    upload,
    loading,
  };
}