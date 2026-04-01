export const marketingTokens = {
  container: "mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8",
  sectionSpacing: "py-16 sm:py-20 lg:py-28",
  headingScale: {
    display: "text-5xl font-bold tracking-tight text-[#062040] sm:text-6xl lg:text-7xl",
    h2: "text-3xl font-bold tracking-tight text-[#062040] sm:text-4xl",
    h3: "text-xl font-bold tracking-tight text-[#062040] sm:text-2xl",
    body: "text-base leading-7 text-slate-600",
    muted: "text-sm leading-6 text-slate-500",
  },
  buttonVariants: {
    // Dark navy — primary action ("Try the Demo")
    primary:
      "inline-flex items-center justify-center rounded-full bg-[#062040] px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0a3060] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#062040] focus-visible:ring-offset-2",
    // Blue outlined — secondary action ("Check Our Prices")
    secondary:
      "inline-flex items-center justify-center rounded-full border-2 border-[#1B6EF3] bg-[#1B6EF3] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#1558c9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] focus-visible:ring-offset-2",
    // Ghost — tertiary / login link
    ghost:
      "inline-flex items-center justify-center px-4 py-2 text-sm font-semibold text-[#062040] transition hover:text-[#1B6EF3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] focus-visible:ring-offset-2",
  },
  surfaces: {
    page: "bg-[#EBF2FA] text-[#062040]",
    card: "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm",
    subtle: "rounded-2xl bg-[#F4F8FC] p-6",
    accent: "rounded-3xl bg-[#062040] text-white",
    dark: "rounded-2xl bg-[#062040] p-7 text-white",
  },
};
