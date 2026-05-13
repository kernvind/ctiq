import Image from "next/image";
import { prisma } from "@repo/db";

export default async function Home() {
  const user = await prisma.user.findFirst();
  return (
    <div className="flex min-h-screen flex-col bg-white">
      {user?.name ?? "No user added yet"}
      <main className="flex-1">
        <section className="container mx-auto px-4 py-32">
          <div>
            <h1 className="text-5xl font-bold text-gray-900 mb-4">
              Welcome to the Web Dashboard
            </h1>
          </div>
        </section>
      </main>
    </div>
  );
}
