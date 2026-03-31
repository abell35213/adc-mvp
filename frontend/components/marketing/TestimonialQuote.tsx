import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function TestimonialQuote() {
  return (
    <section className="bg-white border-t border-slate-200 py-14 sm:py-18">
      <MarketingContainer>
        <figure className={`${marketingTokens.surfaces.accent} p-10 sm:p-14`}>
          <div className="mx-auto max-w-3xl text-center">
            <svg className="mx-auto mb-6 h-8 w-8 text-sky-400" fill="currentColor" viewBox="0 0 32 32" aria-hidden="true">
              <path d="M9.352 4C4.456 7.456 1 13.12 1 19.36c0 5.088 3.072 8.064 6.624 8.064 3.36 0 5.856-2.688 5.856-5.856 0-3.168-2.208-5.472-5.088-5.472-.576 0-1.344.096-1.536.192.48-3.264 3.552-7.104 6.624-9.024L9.352 4zm16.512 0c-4.8 3.456-8.256 9.12-8.256 15.36 0 5.088 3.072 8.064 6.624 8.064 3.264 0 5.856-2.688 5.856-5.856 0-3.168-2.304-5.472-5.184-5.472-.576 0-1.248.096-1.44.192.48-3.264 3.456-7.104 6.528-9.024L25.864 4z" />
            </svg>
            <blockquote className="text-xl font-medium leading-9 text-white sm:text-2xl">
              ADC cut our investigation prep from hours to minutes. We finally have one defensible source of truth.
            </blockquote>
            <figcaption className="mt-8 flex items-center justify-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-500/30 text-sm font-bold text-white">JL</div>
              <div className="text-left">
                <p className="text-sm font-semibold text-white">Jordan Lee</p>
                <p className="text-xs text-sky-300">Director of Safety Operations, NorthLine Freight</p>
              </div>
            </figcaption>
          </div>
        </figure>
      </MarketingContainer>
    </section>
  );
}
