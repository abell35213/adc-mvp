import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ADC Dashboard",
  description: "Accident Documentation & Compliance Dashboard",
};

const deployVersion = process.env.NEXT_PUBLIC_DEPLOY_VERSION ?? "dev";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased bg-[#EBF2FA]">
        {children}
        <div className="fixed bottom-2 right-2 rounded bg-slate-900/85 px-2 py-1 text-xs text-white" aria-label="deploy-version">
          Deploy {deployVersion}
        </div>
      </body>
    </html>
  );
}