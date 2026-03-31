export const navyColors = {
  dark: "#0a1628",
  mid: "#0f2040",
} as const;

export const marketingTokens = {
  container: "mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8",
  sectionSpacing: "py-14 sm:py-18 lg:py-24",
  headingScale: {
    display: "text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl",
    displayLight: "text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl",
    h2: "text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl",
    h2Light: "text-3xl font-semibold tracking-tight text-white sm:text-4xl",
    h3: "text-xl font-semibold tracking-tight sm:text-2xl",
    body: "text-base leading-7 text-slate-600",
    bodyLight: "text-base leading-7 text-slate-300",
    muted: "text-sm leading-6 text-slate-500",
  },
  buttonVariants: {
    primary:
      "inline-flex items-center justify-center rounded-full bg-sky-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2",
    primaryLight:
      "inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2",
    secondary:
      "inline-flex items-center justify-center rounded-full border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2",
    secondaryLight:
      "inline-flex items-center justify-center rounded-full border border-white/40 bg-white/10 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2",
    ghost:
      "inline-flex items-center gap-1.5 text-sm font-semibold text-sky-600 transition hover:text-sky-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400",
    ghostLight:
      "inline-flex items-center gap-1.5 text-sm font-semibold text-sky-300 transition hover:text-sky-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400",
  },
  surfaces: {
    page: "bg-white text-slate-900",
    card: "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm",
    cardNavy: "rounded-2xl border border-white/10 bg-[#0f2040] p-6",
    subtle: "rounded-2xl border border-slate-200/80 bg-slate-50 p-6",
    accent: "rounded-3xl bg-[#0a1628] text-white",
  },
  badge: "inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700",
  badgeLight: "inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold text-sky-300",
};
