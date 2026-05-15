"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export type LoginState = { error: string } | null;

export async function login(
  _prevState: LoginState,
  formData: FormData
): Promise<LoginState> {
  const username = formData.get("username") as string;
  const password = formData.get("password") as string;

  let response: Response;
  try {
    response = await fetch(`${process.env.BACKEND_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    return { error: "Network error. Please try again." };
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    return { error: errorData.message || "Login failed" };
  }

  const data = await response.json();
  const cookieStore = await cookies();
  cookieStore.set("token", data.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });

  redirect("/");
}
