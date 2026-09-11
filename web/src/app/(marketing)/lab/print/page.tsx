"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ThermalPrint } from "@/components/thermal/ThermalPrint";
import {
  DEFAULT_OPTIONS,
  type DitherMode,
  type ThermalPrintOptions,
} from "@/lib/thermal-print/shader";

const PAPERS = {
  white: "#f4f3f0",
  grey: "#ecebe8",
  pink: "#f1dad6",
} as const;

type PaperKey = keyof typeof PAPERS;

const SLIDERS: Array<{
  key: keyof Pick<
    ThermalPrintOptions,
    "grain" | "contrast" | "brightness" | "bleed" | "softness" | "dropout" | "streak" | "seed"
  >;
  label: string;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "grain", label: "Grain px", min: 0.5, max: 6, step: 0.1 },
  { key: "contrast", label: "Contrast", min: 0.5, max: 3, step: 0.05 },
  { key: "brightness", label: "Brightness", min: -0.5, max: 0.5, step: 0.01 },
  { key: "bleed", label: "Bleed", min: 0, max: 3, step: 0.1 },
  { key: "softness", label: "Softness", min: 0, max: 0.5, step: 0.01 },
  { key: "dropout", label: "Dropout", min: 0, max: 1, step: 0.01 },
  { key: "streak", label: "Streak", min: 0, max: 0.8, step: 0.01 },
  { key: "seed", label: "Seed", min: 0, max: 100, step: 1 },
];

const SAMPLE_RECEIPT = [
  ["ユニクロ 原宿店", ""],
  ["渋谷区神宮前6-1-9  TEL 03-0000-0000", ""],
  ["2026年08月16日(土) 19:51  レジ#2 No.1801", ""],
  ["------------------------------------------", ""],
  ["ヒートテック", "¥990"],
  ["ソックス", "¥390"],
  ["------------------------------------------", ""],
  ["小　計（税抜 8%）", "¥1,380"],
  ["消費税等（ 8%）", "¥110"],
  ["合　計", "¥1,380"],
  ["クレジット支払", "¥1,380"],
  ["------------------------------------------", ""],
  ["ご利用日", "2026年08月16日"],
  ["会員番号", "************1753"],
  ["支払方法　1回CL", "承認番号 449346"],
  ["伝票番号", "250-626-282-1810"],
  ["", ""],
  ["またのご来店をお待ちしております", ""],
];

export default function PrintLab() {
  const [src, setSrc] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [paper, setPaper] = useState<PaperKey>("white");
  const [showReceipt, setShowReceipt] = useState(true);
  const [size, setSize] = useState(640);
  const [options, setOptions] = useState<ThermalPrintOptions>(DEFAULT_OPTIONS);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    return () => {
      if (src?.startsWith("blob:")) URL.revokeObjectURL(src);
    };
  }, [src]);

  const takeFile = useCallback((file: File | undefined) => {
    if (!file || !file.type.startsWith("image/")) return;
    setSrc((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
  }, []);

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const file = Array.from(event.clipboardData?.files ?? [])[0];
      takeFile(file);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [takeFile]);

  const set = <K extends keyof ThermalPrintOptions>(key: K, value: ThermalPrintOptions[K]) =>
    setOptions((prev) => ({ ...prev, [key]: value }));

  const renderOptions = useMemo<Partial<ThermalPrintOptions>>(
    () => ({ ...options, paper: null }),
    [options],
  );

  const onRender = useCallback((canvas: HTMLCanvasElement) => {
    canvasRef.current = canvas;
  }, []);

  const download = (flatten: boolean) => {
    const source = canvasRef.current;
    if (!source) return;
    let target: HTMLCanvasElement = source;
    if (flatten) {
      target = document.createElement("canvas");
      target.width = source.width;
      target.height = source.height;
      const ctx = target.getContext("2d");
      if (!ctx) return;
      ctx.fillStyle = PAPERS[paper];
      ctx.fillRect(0, 0, target.width, target.height);
      ctx.globalCompositeOperation = "multiply";
      ctx.drawImage(source, 0, 0);
    }
    target.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = flatten ? "thermal-print.png" : "thermal-print-ink.png";
      a.click();
      URL.revokeObjectURL(a.href);
    }, "image/png");
  };

  return (
    <div className="min-h-screen bg-[#161615] p-6 font-mono text-[13px] text-[#e8e6e1] md:p-10">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-8 lg:flex-row lg:items-start">
        <aside className="flex w-full flex-col gap-5 lg:w-[340px] lg:shrink-0">
          <div>
            <h1 className="text-[11px] uppercase tracking-[0.2em] text-[#8a877f]">
              Static Archive · Print lab
            </h1>
            <p className="mt-2 leading-relaxed text-[#a9a59c]">
              Drop an image, paste one, or give a URL. It comes out as thermal
              receipt print. Tune it, then download the ink on transparent or
              flattened onto paper.
            </p>
          </div>

          <label
            className="flex cursor-pointer flex-col items-center justify-center gap-1 border border-dashed border-[#3a3835] px-4 py-6 text-center text-[#a9a59c] transition-colors hover:border-[#8a877f]"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              takeFile(e.dataTransfer.files[0]);
            }}
          >
            <span className="text-[#e8e6e1]">Drop or choose an image</span>
            <span className="text-[11px]">or paste anywhere on the page</span>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => takeFile(e.target.files?.[0])}
            />
          </label>

          <button
            type="button"
            onClick={() => setSrc("/lab-sample.jpg")}
            className="border border-[#3a3835] px-3 py-2 uppercase tracking-[0.14em] text-[#a9a59c] transition-colors hover:border-[#8a877f] hover:text-[#e8e6e1]"
          >
            Use the sample photo
          </button>

          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (urlInput.trim()) setSrc(urlInput.trim());
            }}
          >
            <input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://…/photo.jpg"
              className="min-w-0 flex-1 border border-[#3a3835] bg-transparent px-3 py-2 text-[#e8e6e1] placeholder:text-[#4f4d48] focus:border-[#8a877f] focus:outline-none"
            />
            <button
              type="submit"
              className="border border-[#3a3835] px-3 py-2 uppercase tracking-[0.14em] transition-colors hover:border-[#8a877f]"
            >
              Load
            </button>
          </form>

          <div className="flex flex-col gap-3 border-t border-[#2a2926] pt-5">
            {SLIDERS.map((s) => (
              <label key={s.key} className="grid grid-cols-[90px_1fr_52px] items-center gap-3">
                <span className="text-[#a9a59c]">{s.label}</span>
                <input
                  type="range"
                  min={s.min}
                  max={s.max}
                  step={s.step}
                  value={options[s.key]}
                  onChange={(e) => set(s.key, Number(e.target.value))}
                  className="accent-[#e8e6e1]"
                />
                <span className="text-right tabular-nums">
                  {Number(options[s.key]).toFixed(s.step >= 1 ? 0 : 2)}
                </span>
              </label>
            ))}

            <label className="grid grid-cols-[90px_1fr] items-center gap-3">
              <span className="text-[#a9a59c]">Dither</span>
              <div className="flex gap-1">
                {(["noise", "bayer", "mixed"] as DitherMode[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => set("mode", m)}
                    className={`flex-1 border px-2 py-1.5 uppercase tracking-[0.1em] ${
                      options.mode === m
                        ? "border-[#e8e6e1] bg-[#e8e6e1] text-[#161615]"
                        : "border-[#3a3835] text-[#a9a59c]"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </label>

            <label className="grid grid-cols-[90px_1fr] items-center gap-3">
              <span className="text-[#a9a59c]">Ink</span>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={options.ink}
                  onChange={(e) => set("ink", e.target.value)}
                  className="h-7 w-10 cursor-pointer border border-[#3a3835] bg-transparent"
                />
                <span className="tabular-nums">{options.ink}</span>
              </div>
            </label>

            <label className="grid grid-cols-[90px_1fr] items-center gap-3">
              <span className="text-[#a9a59c]">Paper</span>
              <div className="flex gap-1">
                {(Object.keys(PAPERS) as PaperKey[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPaper(p)}
                    className={`flex-1 border px-2 py-1.5 uppercase tracking-[0.1em] ${
                      paper === p
                        ? "border-[#e8e6e1] bg-[#e8e6e1] text-[#161615]"
                        : "border-[#3a3835] text-[#a9a59c]"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </label>

            <label className="grid grid-cols-[90px_1fr_52px] items-center gap-3">
              <span className="text-[#a9a59c]">Size</span>
              <input
                type="range"
                min={240}
                max={900}
                step={10}
                value={size}
                onChange={(e) => setSize(Number(e.target.value))}
                className="accent-[#e8e6e1]"
              />
              <span className="text-right tabular-nums">{size}</span>
            </label>

            <div className="flex flex-wrap gap-4 pt-1 text-[#a9a59c]">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={options.invert}
                  onChange={(e) => set("invert", e.target.checked)}
                  className="accent-[#e8e6e1]"
                />
                Invert
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showReceipt}
                  onChange={(e) => setShowReceipt(e.target.checked)}
                  className="accent-[#e8e6e1]"
                />
                Receipt under print
              </label>
            </div>
          </div>

          <div className="flex gap-2 border-t border-[#2a2926] pt-5">
            <button
              type="button"
              onClick={() => download(true)}
              disabled={!src}
              className="flex-1 bg-[#e8e6e1] px-3 py-2.5 uppercase tracking-[0.14em] text-[#161615] disabled:opacity-40"
            >
              Download on paper
            </button>
            <button
              type="button"
              onClick={() => download(false)}
              disabled={!src}
              className="flex-1 border border-[#3a3835] px-3 py-2.5 uppercase tracking-[0.14em] disabled:opacity-40"
            >
              Ink only
            </button>
          </div>
        </aside>

        <main className="flex flex-1 items-start justify-center bg-[#d9d8d4] p-8 lg:min-h-[900px]">
          <div
            className="relative overflow-hidden shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_3px_10px_rgba(0,0,0,0.14)]"
            style={{ width: size, height: size, background: PAPERS[paper] }}
          >
            {showReceipt && (
              <div
                className="absolute inset-x-[7%] top-[-6%] flex flex-col gap-[2px] text-[#2a2622]"
                style={{ fontSize: size / 36, lineHeight: 1.35 }}
              >
                {SAMPLE_RECEIPT.map(([left, right], i) => (
                  <div
                    key={i}
                    className={`flex justify-between gap-3 ${
                      i === 0 ? "justify-center text-[1.35em] tracking-[0.06em]" : ""
                    } ${i === 1 || i === 2 || i === SAMPLE_RECEIPT.length - 1 ? "justify-center text-[0.8em]" : ""} ${
                      left === "合　計" ? "text-[1.45em]" : ""
                    }`}
                  >
                    <span className="whitespace-nowrap">{left}</span>
                    {right && <span className="whitespace-nowrap">{right}</span>}
                  </div>
                ))}
              </div>
            )}
            {src ? (
              <ThermalPrint
                src={src}
                width={size}
                height={size}
                options={renderOptions}
                onRender={onRender}
                className="absolute inset-0"
                style={{ mixBlendMode: "multiply" }}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-[#8a877f]">
                No image yet
              </div>
            )}
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                background:
                  "linear-gradient(105deg, rgba(0,0,0,0.05) 0%, rgba(255,255,255,0.18) 35%, rgba(255,255,255,0) 60%, rgba(0,0,0,0.04) 100%)",
              }}
            />
          </div>
        </main>
      </div>
    </div>
  );
}
