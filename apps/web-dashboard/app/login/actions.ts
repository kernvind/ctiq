"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { gql } from "graphql-request";
import { graphqlClient } from "@/lib/graphql-client";

export type LoginState = { error: string } | null;

const LOGIN_MUTATION = gql`
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      token
    }
  }
`;

export async function login(
  _prevState: LoginState,
  formData: FormData
): Promise<LoginState> {
  const username = formData.get("username") as string;
  const password = formData.get("password") as string;

  let data: { login: { token: string } };
  try {
    data = await graphqlClient.request(LOGIN_MUTATION, {
      input: { username, password },
    });
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Login failed";
    return { error: message };
  }

  const cookieStore = await cookies();
  cookieStore.set("token", data.login.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });

  redirect("/dashboard");
}
