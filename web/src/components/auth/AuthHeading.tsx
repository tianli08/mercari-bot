import { Dashes } from "@/components/marketing/Sheet";

export function AuthHeading({ children }: { children: React.ReactNode }) {
  return (
    <>
      <h1 className="ink text-center text-[20px] uppercase tracking-[0.06em]">
        <span className="tall-block tall-block-center">{children}</span>
      </h1>
      <Dashes />
    </>
  );
}
