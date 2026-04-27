import Link from "next/link";

export interface HelpArticle {
  title: string;
  href: string;
  description: string;
  readTime: string;
  audience: string;
}

interface HelpArticleCardProps {
  article: HelpArticle;
}

export default function HelpArticleCard({ article }: HelpArticleCardProps) {
  return (
    <article className="rounded-lg border border-border-subtle bg-surface p-4 shadow-card">
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-status-info-soft px-2 py-0.5 text-status-info">{article.audience}</span>
        <span className="rounded-full bg-surface-raised px-2 py-0.5 text-text-muted">{article.readTime}</span>
      </div>
      <h3 className="mt-3 text-base font-semibold text-text-primary">
        <Link href={article.href} className="hover:underline">
          {article.title}
        </Link>
      </h3>
      <p className="mt-1 text-sm text-text-secondary">{article.description}</p>
    </article>
  );
}
