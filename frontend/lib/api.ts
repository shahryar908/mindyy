const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type SignupResponse = {
  user_id: string;
  email: string;
  message: string;
};

export type UserRead = {
  id: string;
  email: string;
  is_verified: boolean;
};

const ACCESS_KEY = "mindyy_access";
const REFRESH_KEY = "mindyy_refresh";

export const tokenStore = {
  getAccess: () => (typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY)),
  getRefresh: () => (typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY)),
  set: (pair: { access_token: string; refresh_token: string }) => {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) detail = body.detail[0].msg;
  } catch {
    /* ignore */
  }
  return new ApiError(res.status, detail);
}

async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean; retry?: boolean } = {},
): Promise<T> {
  const { auth, retry = true, headers, ...rest } = options;
  const h = new Headers(headers);
  if (!h.has("Content-Type") && rest.body) h.set("Content-Type", "application/json");
  if (auth) {
    const token = tokenStore.getAccess();
    if (token) h.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_URL}${path}`, { ...rest, headers: h });

  if (res.status === 401 && auth && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, { ...options, retry: false });
    }
    tokenStore.clear();
  }

  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
  const refresh_token = tokenStore.getRefresh();
  if (!refresh_token) return false;
  try {
    const res = await fetch(`${API_URL}/auth/refresh-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!res.ok) return false;
    const pair = (await res.json()) as TokenPair;
    tokenStore.set(pair);
    return true;
  } catch {
    return false;
  }
}

export const api = {
  signup: (email: string, password: string) =>
    request<SignupResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  verifyOtp: (user_id: string, code: string) =>
    request<TokenPair>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ user_id, code }),
    }),

  resendOtp: (email: string) =>
    request<{ message: string }>("/auth/resend-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  signin: (email: string, password: string) =>
    request<TokenPair>("/auth/signin", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }),

  logout: () => request<{ message: string }>("/auth/logout", { method: "POST", auth: true }),

  me: () => request<UserRead>("/auth/me", { auth: true }),

  googleLoginUrl: () => `${API_URL}/auth/google/login`,
};
