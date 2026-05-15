"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export type SignupState = { error: string } | null;

export async function signup(
  _prevState: SignupState,
  formData: FormData
): Promise<SignupState> {
  const username = formData.get("username") as string;
  const email = formData.get("email") as string;
  const name = formData.get("name") as string;
  const password = formData.get("password") as string;
  const confirmPassword = formData.get("confirmPassword") as string;

  if (password !== confirmPassword) {
    return { error: "Passwords do not match" };
  }

  let response: Response;
  try {
    response = await fetch(`${process.env.BACKEND_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, name: name || undefined }),
    });
  } catch {
    return { error: "Network error. Please try again." };
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    return { error: errorData.message || "Signup failed" };
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
