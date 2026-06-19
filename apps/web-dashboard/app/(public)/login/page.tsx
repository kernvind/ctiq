import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LoginForm } from "@/app/(public)/login/_components/login-form";

export default async function Page() {
  const cookieStore = await cookies();
  const token = cookieStore.get("token");

  if (token) {
    redirect("/dashboard");
  }

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-sm">
        <LoginForm />
      </div>
    </div>
  );
}
