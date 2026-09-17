import type { Metadata } from "next";
import { SignUp } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { authCardAppearance } from "@/lib/clerk-appearance";

export const metadata: Metadata = { title: "Sign up — Static Archive" };

export default async function Page() {
  const { isAuthenticated } = await auth();
  if (isAuthenticated) redirect("/dashboard");
  return <SignUp path="/signup" routing="path" appearance={authCardAppearance} />;
}
