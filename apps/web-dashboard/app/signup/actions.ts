"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { sdk } from "@repo/generated-schemas-web";
import { flattenZodErrors } from "@/lib/zod-errors";
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
  });
  if (!result.success) {
    return { error: flattenZodErrors(result.error) };
  }
  const { username, email, name, password } = result.data;
  const confirmPassword = formData.get("confirmPassword") as string;

  if (password !== confirmPassword) {
    return { error: "Passwords do not match" };
  }

  let token: string;
  try {
    const data = await sdk.signup_mutation({
      input: { username, email, password, name: name || undefined },
    });
    token = data.signup.token;
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Signup failed";
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
