import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "HIVE MIND — Swarm Intelligence Prediction Engine",
  description:
    "Simulate thousands of interacting agents, watch emergent behavior in 3D, and read the prediction report. Rehearse the future in a digital sandbox.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Header />
        <main className="min-h-[calc(100vh-9rem)]">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
