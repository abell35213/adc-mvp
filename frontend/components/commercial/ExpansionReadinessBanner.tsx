interface ExpansionReadinessBannerProps {
  readyMarkets: number;
  blockedMarkets: number;
}

export default function ExpansionReadinessBanner({ readyMarkets, blockedMarkets }: ExpansionReadinessBannerProps) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
      <p className="font-semibold">Expansion readiness snapshot</p>
      <p>
        {readyMarkets} markets ready to launch. {blockedMarkets} markets need blocker remediation.
      </p>
    </div>
  );
}
