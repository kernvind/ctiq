"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { gql } from "graphql-request";
import { graphqlClient } from "@/lib/graphql-client";

export type SignupState = { error: string } | null;

const SIGNUP_MUTATION = gql`
  mutation Signup($input: SignupInput!) {
    signup(input: $input) {
      token
    }
  }
`;

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

  let data: { signup: { token: string } };
  try {
    data = await graphqlClient.request(SIGNUP_MUTATION, {
      input: { username, email, password, name: name || undefined },
    });
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Signup failed";
    return { error: message };
  }

  const cookieStore = await cookies();
  cookieStore.set("token", data.signup.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });

  redirect("/dashboard");
}
