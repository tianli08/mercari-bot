import type { Metadata } from "next";
import { SignIn } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { authCardAppearance } from "@/lib/clerk-appearance";

export const metadata: Metadata = { title: "Log in — Static Archive" };

export default async function Page() {
  const { isAuthenticated } = await auth();
  if (isAuthenticated) redirect("/dashboard");
  return <div className="flex flex-col gap-5">
    <SignIn path="/login" routing="path" appearance={authCardAppearance} />
    <Link href="/reset-password" className="text-center text-[13px] underline">Forgot password?</Link>
  </div>;
}
