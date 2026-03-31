import type { Metadata } from "next";
import { buildPageMetadata } from "../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "ADC Solutions",
  "Explore ADC solutions for fleet safety, claims defense, and compliance teams.",
  "/solutions",
);

export default function SolutionsIndexPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="text-3xl font-bold">Solutions</h1>
      <p className="mt-2 text-slate-700">Choose a workflow built for your team&apos;s priorities.</p>
    </main>
  );
}
