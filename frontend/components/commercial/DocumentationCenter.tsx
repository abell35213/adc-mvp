import Link from "next/link";

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
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h3>
      <ul className="mt-3 space-y-2">
        {docs.map((doc) => (
          <li key={doc.href} className="rounded border p-3 dark:border-gray-700">
            <Link href={doc.href} className="font-medium text-blue-600 hover:underline dark:text-blue-400">
              {doc.title}
            </Link>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{doc.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
