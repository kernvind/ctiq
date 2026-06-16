"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { sdk } from "@repo/generated-schemas-web";
import { flattenZodErrors } from "@/lib/zod-errors";
import { ZodLoginSchema } from "@repo/zod-validations";

export type LoginState = { error: string } | null;

export async function login(
  _prevState: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const result = ZodLoginSchema.safeParse({
    username: formData.get("username"),
    password: formData.get("password"),
  });
  if (!result.success) {
    return { error: flattenZodErrors(result.error) };
  }
  let token: string;
  try {
    const data = await sdk.login_mutation({ input: result.data });
    token = data.login.token;
  } catch (err: unknown) {
    console.log("Login error:", err);
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Login failed";
    return { error: message };
  }

  const cookieStore = await cookies();
  cookieStore.set("token", token, {
    httpOnly: true,
    // COOKIE_SECURE=true only when serving over HTTPS (staging/prod).
    // NODE_ENV=production is not the right signal — Docker local is HTTP.
    secure: process.env.COOKIE_SECURE === "true",
    sameSite: "lax",
    path: "/",
  });

  redirect("/dashboard");
}
