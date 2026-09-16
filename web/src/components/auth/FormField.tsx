"use client";

import { type InputHTMLAttributes, useId } from "react";

type FormFieldProps = {
  /** Visible label rendered above the input. */
  label: string;
  /** Optional helper text shown below the input (e.g. password requirements). */
  helper?: string;
  /** Inline error message. When set, the field is marked invalid via aria. */
  error?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "aria-invalid" | "aria-describedby">;

/**
 * A labelled input with an inline-error slot, sized for the auth forms.
 * No signup-specific logic — plans 4.3.3 and 4.3.5 reuse this as-is.
 */
export function FormField({ label, helper, error, className = "", ...rest }: FormFieldProps) {
  const id = useId();
  const helperId = `${id}-helper`;
  const errorId = `${id}-error`;

  const describedBy = [helper && !error ? helperId : null, error ? errorId : null]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={id}
        className="text-[11px] uppercase tracking-[0.16em] text-ink-dim"
      >
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={[
          "w-full rounded-none border-2 border-ink bg-paper-white px-3 py-2 text-[16px] text-ink",
          "placeholder:text-ink-faded",
          "focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-2 focus:ring-offset-background",
          error ? "border-stamp" : "",
          className,
        ].join(" ")}
        {...rest}
      />
      {helper && !error && (
        <p id={helperId} className="text-[11px] text-ink-faded">
          {helper}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-[12px] text-stamp">
          {error}
        </p>
      )}
    </div>
  );
}
