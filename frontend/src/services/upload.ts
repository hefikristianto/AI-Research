import api from "@/lib/axios";

export async function uploadChart(formData: FormData) {
  const { data } = await api.post("/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return data;
}