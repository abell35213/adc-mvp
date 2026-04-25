import Link from "next/link";
import { designTokens } from "@/lib/design/tokens";

export interface DocumentationLink {
  title: string;
  href: string;
  description: string;
}

interface DocumentationCenterProps {
  title?: string;
  docs: DocumentationLink[];
}

export default function DocumentationCenter({ title = "Documentation center", docs }: DocumentationCenterProps) {
  return (
    <section className={`${designTokens.surface.base} p-4`}>
      <h3 className="text-base font-semibold text-text-primary">{title}</h3>
      <ul className="mt-3 space-y-2">
        {docs.map((doc) => (
          <li key={doc.href} className="rounded-md border border-border-subtle p-3">
            <Link href={doc.href} className={`font-medium ${designTokens.accent.text}`}>
              {doc.title}
            </Link>
            <p className="mt-1 text-sm text-text-secondary">{doc.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
