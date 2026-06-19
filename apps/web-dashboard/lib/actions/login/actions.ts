"use server";

import { redirect } from "next/navigation";
import { sdk } from "@repo/generated-schemas-web";
import { flattenZodErrors } from "@/lib/zod-errors";
import { setAuthCookies } from "@/lib/auth-cookies";
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
  let accessToken: string;
  let refreshToken: string;
  try {
    const data = await sdk.login_mutation({ input: result.data });
    accessToken = data.login.accessToken;
    refreshToken = data.login.refreshToken;
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Login failed";
    return { error: message };
  }

  await setAuthCookies(accessToken, refreshToken);
  redirect("/dashboard");
}
