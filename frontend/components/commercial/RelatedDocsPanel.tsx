import DocumentationCenter, { type DocumentationLink } from "./DocumentationCenter";

interface RelatedDocsPanelProps {
  docs: DocumentationLink[];
}

export default function RelatedDocsPanel({ docs }: RelatedDocsPanelProps) {
  return (
    <aside>
      <DocumentationCenter title="Related docs" docs={docs} />
    </aside>
  );
}
