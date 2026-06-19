import { SignupForm } from "@/app/(public)/signup/_components/signup-form";

export default function Page() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-sm">
        <SignupForm />
      </div>
    </div>
  );
}
