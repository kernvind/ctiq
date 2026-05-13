import Image from "next/image";
import {prisma} from "@repo/db";

export default async function Home() {
  const user = await prisma.user.findFirst();
  return <div className="flex min-h-screen flex-col bg-white">{user?.name ?? "No user added yet"}</div>;
}