import { ReactNode } from "react";
import { marketingTokens } from "@/components/marketing/tokens";

type MarketingContainerProps = {
  children: ReactNode;
  className?: string;
};

export function MarketingContainer({ children, className = "" }: MarketingContainerProps) {
  return <div className={`${marketingTokens.container} ${className}`.trim()}>{children}</div>;
}

type MarketingSectionProps = {
  children: ReactNode;
  className?: string;
  id?: string;
};

export function MarketingSection({ children, className = "", id }: MarketingSectionProps) {
  return (
    <section id={id} className={`${marketingTokens.sectionSpacing} ${className}`.trim()}>
      <MarketingContainer>{children}</MarketingContainer>
    </section>
  );
}
