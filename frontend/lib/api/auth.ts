/* ── Auth ──────────────────────────────────────────────────────── */

import { request } from "./core";

export interface MeResponse {
  user_id: string;
  email: string;
  role: string;
  org_ids: string[];
}

export function getMe() {
  return request<MeResponse>("/auth/me");
}

export interface LoginResponse {
  user: MeResponse;
}

export async function login(email: string, password: string) {
  await request<void>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const user = await getMe();
  return { user } satisfies LoginResponse;
}

export interface RegisterResponse {
  user: MeResponse;
  user_id: string;
  email: string;
  role: string;
  org_id: string;
}

export async function register(
  email: string,
  password: string,
  role = "safety_manager",
  orgName = "Default"
) {
  const data = await request<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, role, org_name: orgName }),
  });
  const user = await getMe();
  return { ...data, user };
}

export function logout() {
  return request<void>("/auth/logout", {
    method: "POST",
  }).finally(() => {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  });
}
