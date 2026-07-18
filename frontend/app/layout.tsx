import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";

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
      <body className="bg-page text-text-primary antialiased">
        <AuthProvider>{children}</AuthProvider>
        <div className="fixed bottom-2 right-2 rounded-md bg-shell/90 px-2 py-1 text-xs text-text-inverse" aria-label="deploy-version">
          Deploy {deployVersion}
        </div>
      </body>
    </html>
  );
}