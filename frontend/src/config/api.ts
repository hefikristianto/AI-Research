const configuredApiUrl = (
  process.env.NEXT_PUBLIC_API_URL
  ?? "http://127.0.0.1:8000"
);

export const API_URL = configuredApiUrl.replace(
  /\/$/,
  "",
);
