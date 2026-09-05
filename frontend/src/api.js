export function currentUser() {
  return localStorage.getItem("delta_user") || "";
}

function responseError(detail, fallback) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (detail && typeof detail.message === "string") return detail.message;
  return fallback || "Request failed";
}

export async function api(path, method = "GET", body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-Username": currentUser() },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(responseError(data.detail, res.statusText));
    err.status = res.status;
    throw err;
  }
  return data;
}

export function timeAgo(iso) {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export function rupees(n) {
  return `₹${n.toLocaleString("en-IN")}`;
}

export function scoreTone(score) {
  if (score >= 60) return "alert";
  if (score >= 30) return "warn";
  return "calm";
}
