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
    const data = await sdk.Login({ input: result.data });
    token = data.login.token;
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Login failed";
    return { error: message };
  }

  const cookieStore = await cookies();
  cookieStore.set("token", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });

  redirect("/dashboard");
}
