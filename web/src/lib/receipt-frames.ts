// Server-side discovery of hero frames.
//
// Any image dropped into `public/frames/` becomes a frame in the hero loop.
// No naming convention: files are sorted naturally (so "shot 2" comes before
// "shot 10") and each is paired with the next receipt template, cycling if
// there are more images than templates.

import { readdirSync } from "node:fs";
import path from "node:path";

import { RECEIPT_TEMPLATES, type ReceiptFrame } from "@/lib/marketing-content";

const FRAMES_DIR = path.join(process.cwd(), "public", "frames");
const IMAGE_FILE = /\.(jpe?g|png|webp|avif|gif)$/i;

export function getReceiptFrames(): ReceiptFrame[] {
  let files: string[] = [];
  try {
    files = readdirSync(FRAMES_DIR).filter(
      (name) => IMAGE_FILE.test(name) && !name.startsWith("."),
    );
  } catch {
    files = [];
  }
  files.sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }),
  );
  return files.map((file, i) => ({
    ...RECEIPT_TEMPLATES[i % RECEIPT_TEMPLATES.length],
    image: `/frames/${encodeURIComponent(file)}`,
  }));
}
