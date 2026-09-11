"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { tintClass } from "@/components/marketing/Sheet";
import type { ReceiptFrame } from "@/lib/marketing-content";
import {
  createThermalPrinter,
  loadImage,
  type ThermalPrintOptions,
} from "@/lib/thermal-print/shader";

/** Hero prints are rendered at this width; the receipt text scales from it. */
const HERO_SIZE = 680;
/** Portrait height for the hero print so it can cover a tall frame without upscaling much. */
const HERO_PRINT_HEIGHT = 1040;
const STRIP_SIZE = 160;
const FRAME_MS = 300;
/** Width the optimizer serves the source photo at. Must be in Next's deviceSizes. */
const SOURCE_WIDTH = 1080;

const PRINT_OPTIONS: Partial<ThermalPrintOptions> = {
  grain: 1.6,
  contrast: 1.35,
  brightness: 0.02,
  bleed: 0.8,
  softness: 0.12,
  dropout: 0.12,
  streak: 0.18,
  mode: "noise",
  ink: "#1c1a17",
};

/** Route the photo through Next's image optimizer so the shader never sees a 24MP original. */
function optimizedSrc(src: string): string {
  return `/_next/image?url=${encodeURIComponent(src)}&w=${SOURCE_WIDTH}&q=75`;
}

interface FramePrints {
  hero: (HTMLCanvasElement | null)[];
  strip: (HTMLCanvasElement | null)[];
}

/**
 * Print every frame through the shader on one hidden WebGL canvas, copying
 * each result into a plain 2D canvas as it finishes so frames appear one by
 * one. No PNG encoding, and only one GL context for the whole page.
 */
function useThermalFrames(frames: readonly ReceiptFrame[]): FramePrints {
  const [prints, setPrints] = useState<FramePrints>(() => ({
    hero: frames.map(() => null),
    strip: frames.map(() => null),
  }));

  useEffect(() => {
    let cancelled = false;
    const gl = document.createElement("canvas");
    let printer: ReturnType<typeof createThermalPrinter>;
    try {
      printer = createThermalPrinter(gl);
    } catch {
      return;
    }
    const dpr = Math.min(2, window.devicePixelRatio || 1);

    const printAt = (image: HTMLImageElement, width: number, height: number, seed: number) => {
      gl.width = Math.round(width * dpr);
      gl.height = Math.round(height * dpr);
      printer.render(image, { ...PRINT_OPTIONS, seed });
      const out = document.createElement("canvas");
      out.width = gl.width;
      out.height = gl.height;
      out.style.width = "100%";
      out.style.height = "100%";
      out.style.objectFit = "cover";
      out.style.display = "block";
      out.getContext("2d")?.drawImage(gl, 0, 0);
      return out;
    };

    (async () => {
      for (let i = 0; i < frames.length; i++) {
        let image: HTMLImageElement;
        try {
          image = await loadImage(optimizedSrc(frames[i].image));
        } catch {
          try {
            image = await loadImage(frames[i].image);
          } catch {
            continue;
          }
        }
        if (cancelled) return;
        const seed = 7 + i * 11;
        const hero = printAt(image, HERO_SIZE, HERO_PRINT_HEIGHT, seed);
        const strip = printAt(image, STRIP_SIZE, STRIP_SIZE, seed);
        setPrints((prev) => {
          const next = { hero: [...prev.hero], strip: [...prev.strip] };
          next.hero[i] = hero;
          next.strip[i] = strip;
          return next;
        });
        // Let the browser paint between frames.
        await new Promise((r) => requestAnimationFrame(() => r(null)));
      }
    })();

    return () => {
      cancelled = true;
      printer.destroy();
    };
  }, [frames]);

  return prints;
}

/** Mounts a prepared canvas element into the DOM, moving it if it changes. */
function PrintLayer({ canvas }: { canvas: HTMLCanvasElement | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (canvas) el.replaceChildren(canvas);
    else el.replaceChildren();
  }, [canvas]);
  return (
    <div
      ref={ref}
      className="pointer-events-none absolute inset-0"
      style={{ mixBlendMode: "multiply" }}
      aria-hidden
    />
  );
}

function ReceiptUnderPrint({ frame, scale }: { frame: ReceiptFrame; scale: number }) {
  const fs = 18 * scale;
  return (
    <div
      className="ink font-jp absolute"
      style={{
        left: `${9}%`,
        right: `${9}%`,
        top: frame.offset * scale,
        fontSize: fs,
        lineHeight: 1.35,
      }}
    >
      <div className="text-center" style={{ fontSize: fs * 1.35, letterSpacing: "0.06em" }}>
        <span className="tall" style={{ transformOrigin: "top center" }}>{frame.shop}</span>
      </div>
      <div className="text-center text-ink-dim" style={{ fontSize: fs * 0.8, lineHeight: 1.4 }}>
        {frame.address}
        <br />
        TEL 03-0000-0000
        <br />
        {frame.datetime} {frame.register}
      </div>
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      {frame.items.map(([name, price]) => (
        <div key={name} className="flex justify-between gap-3">
          <span>{name}</span>
          <span>{price}</span>
        </div>
      ))}
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      <div className="flex justify-between gap-3">
        <span>小　計（税抜 8%）</span>
        <span>{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>消費税等（ 8%）</span>
        <span>{frame.tax}</span>
      </div>
      <div className="flex justify-between gap-3" style={{ fontSize: fs * 1.45, margin: "2px 0" }}>
        <span className="tall">合　計</span>
        <span className="tall">{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>（内消費税等 8%）</span>
        <span>—</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>クレジット支払</span>
        <span>{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>お買上明細</span>
        <span />
      </div>
      <div className="text-ink-dim" style={{ fontSize: fs * 0.8, marginTop: 6 * scale }}>
        [*]マークは軽減税率対象商品です。
      </div>
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      <div className="flex justify-between gap-3">
        <span>ご利用日</span>
        <span>{frame.datetime.slice(0, 11)}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>会員番号</span>
        <span>{frame.member}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>支払方法　1回CL</span>
        <span>承認番号 {frame.approval}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>金額</span>
        <span>{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>伝票番号</span>
        <span>{frame.slip}</span>
      </div>
      <div
        className="font-barcode text-center leading-none"
        style={{ fontSize: fs * 3.6, marginTop: 8 * scale }}
        aria-hidden
      >
        {`SA${frame.slip.replace(/-/g, "").slice(0, 8)}`}
      </div>
      <div className="text-center text-ink-dim" style={{ fontSize: fs * 0.8, marginTop: 8 * scale }}>
        またのご来店をお待ちしております
      </div>
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs, marginTop: 10 * scale }}>
        {"-".repeat(60)}
      </div>
      <div className="flex justify-between gap-3">
        <span>ポイント残高</span>
        <span>{frame.approval.slice(0, 3)},{frame.approval.slice(3)} P</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>今回獲得ポイント</span>
        <span>{frame.tax.replace("¥", "")} P</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>有効期限</span>
        <span>2027年08月31日</span>
      </div>
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      <div className="text-ink-dim" style={{ fontSize: fs * 0.8, lineHeight: 1.5 }}>
        返品・交換はレシートをご持参のうえ、購入日より7日以内にお願いいたします。
        <br />
        営業時間 11:00〜20:00　定休日 なし
      </div>
      <div className="flex justify-between gap-3" style={{ marginTop: 6 * scale }}>
        <span>担当</span>
        <span>{frame.register.slice(-4)}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>レシートNo.</span>
        <span>{frame.slip.split("-").reverse().join("")}</span>
      </div>
      <div className="text-center" style={{ fontSize: fs * 1.15, marginTop: 10 * scale, letterSpacing: "0.1em" }}>
        <span className="tall" style={{ transformOrigin: "top center" }}>{frame.shop.split(" ")[0]}</span>
      </div>
    </div>
  );
}

function ScannedFrame({
  frame,
  print,
  scale,
  index,
  size,
}: {
  frame: ReceiptFrame;
  print: HTMLCanvasElement | null;
  /** Receipt text scale relative to a 680px-wide sheet. */
  scale: number;
  index: number;
  /** Fixed square size in px; omit to fill the parent. */
  size?: number;
}) {
  return (
    <div
      className={`sheet overflow-hidden ${tintClass(frame.tint)} ${size === undefined ? "absolute inset-0" : "relative"}`}
      style={size === undefined ? undefined : { width: size, height: size }}
    >
      <ReceiptUnderPrint frame={frame} scale={scale} />
      <PrintLayer canvas={print} />
      <span className="sr-only">Frame {index + 1}</span>
    </div>
  );
}

/**
 * Hero square looping the frames, the receipts column beside it (passed as
 * children), and the strip of every frame below. One component so the
 * frames are loaded and printed exactly once for both.
 */
export function ReceiptFrames({
  frames,
  loopLabel,
  children,
}: {
  frames: readonly ReceiptFrame[];
  loopLabel: string;
  children: ReactNode;
}) {
  const prints = useThermalFrames(frames);
  const [tick, setTick] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  const ready = prints.hero.flatMap((p, i) => (p ? [i] : []));
  const current = ready.length ? ready[tick % ready.length] : 0;

  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const update = () => setScale(el.clientWidth / HERO_SIZE);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (ready.length < 2) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setTick((t) => t + 1), FRAME_MS);
    return () => window.clearInterval(id);
  }, [ready.length]);

  return (
    <>
      <section className="mt-12 grid grid-cols-1 items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-stretch lg:gap-10 xl:grid-cols-[680px_minmax(0,1fr)] xl:gap-14">
        {frames.length > 0 && (
          <div className="flex w-full max-w-[680px] flex-col lg:max-w-none">
            {/* Square on small screens; on large ones stretches to the receipts beside it. */}
            <div ref={heroRef} className="relative aspect-square w-full lg:aspect-auto lg:flex-1">
              <ScannedFrame
                frame={frames[current]}
                print={prints.hero[current]}
                scale={scale}
                index={current}
              />
            </div>
            <div className="mt-3 text-[11px] uppercase tracking-[0.16em] text-ink-dim">
              {loopLabel}
            </div>
          </div>
        )}
        <div className="flex min-w-0 flex-col gap-6">{children}</div>
      </section>

      {frames.length > 0 && (
        <section aria-label="All frames" className="mt-16 md:mt-[72px]">
          <div className="flex gap-5 overflow-x-auto pb-2 pt-1">
            {frames.map((frame, i) => (
              <div
                key={frame.image}
                className="shrink-0"
                style={{ transform: `rotate(${[-1.5, 1, -0.5, 1.5, -1, 0.5, -1.5, 1][i % 8]}deg)` }}
              >
                <ScannedFrame frame={frame} print={prints.strip[i]} scale={STRIP_SIZE / HERO_SIZE} size={STRIP_SIZE} index={i} />
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
