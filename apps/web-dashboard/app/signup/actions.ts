"use server";

import { redirect } from "next/navigation";
import { sdk } from "@repo/generated-schemas-web";
import { flattenZodErrors } from "@/lib/zod-errors";
import { setAuthCookies } from "@/lib/auth-cookies";
import { ZodRegisterFormSchema } from "@repo/zod-validations";

export type SignupState = { error: string } | null;

export async function signup(
  _prevState: SignupState,
  formData: FormData,
): Promise<SignupState> {
  const result = ZodRegisterFormSchema.safeParse({
    username: formData.get("username"),
    email: formData.get("email"),
    name: formData.get("name"),
    password: formData.get("password"),
    confirmPassword: formData.get("confirmPassword"),
    role: formData.get("role"),
  });
  if (!result.success) {
    return { error: flattenZodErrors(result.error) };
  }
  const { username, email, name, password, role } = result.data;
  const confirmPassword = formData.get("confirmPassword") as string;

  if (password !== confirmPassword) {
    return { error: "Passwords do not match" };
  }

  let accessToken: string;
  let refreshToken: string;
  try {
    const data = await sdk.signup_mutation({
      input: { username, email, password, name: name || undefined, role },
    });
    accessToken = data.signup.accessToken;
    refreshToken = data.signup.refreshToken;
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Signup failed";
    return { error: message };
  }

  await setAuthCookies(accessToken, refreshToken);
  redirect("/dashboard");
}
