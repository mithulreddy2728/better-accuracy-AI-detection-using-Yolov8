// API URL Helper Configuration
// Automatically detects environment (local dev vs Docker production / ngrok / custom domain)
export const getApiUrl = (path = "") => {
  const base = window.location.port === "3000" ? "http://localhost:8000" : window.location.origin;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
};
