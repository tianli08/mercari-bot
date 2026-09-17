import type { Metadata } from "next";
import { SignIn } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { authCardAppearance } from "@/lib/clerk-appearance";

export const metadata: Metadata = { title: "Log in — Static Archive" };

export default async function Page() {
  const { isAuthenticated } = await auth();
  if (isAuthenticated) redirect("/dashboard");
  return <SignIn path="/login" routing="path" appearance={authCardAppearance} />;
}
