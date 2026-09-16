"use client";

import type { ButtonHTMLAttributes } from "react";

type SubmitButtonProps = {
  /** Whether a request is currently in flight. Disables the button and shows pending state. */
  pending?: boolean;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "disabled">;

/**
 * A submit button that renders a pending state and disables itself while
 * in flight. Visual style matches the landing page's primary CTA.
 */
export function SubmitButton({ pending = false, children, className = "", ...rest }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={pending}
      className={[
        "w-full border-2 border-ink bg-ink px-4 py-2.5 text-[15px] uppercase tracking-[0.12em] text-paper-white",
        "transition-opacity hover:opacity-80",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      ].join(" ")}
      {...rest}
    >
      {pending ? "···" : children}
    </button>
  );
}
