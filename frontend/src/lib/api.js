const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function buildQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      search.set(key, value);
    }
  });
  return search.toString();
}

export async function requestJson(path, params = {}, method = "GET") {
  const query = buildQuery(params);
  const response = await fetch(`${DEFAULT_API_BASE_URL}${path}${query ? `?${query}` : ""}`, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) {
        message = body.detail;
      }
    } catch {
      // Ignore JSON parsing and keep the fallback message.
    }
    throw new Error(message);
  }

  return response.json();
}
