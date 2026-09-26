import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import "@/app/globals.css";

// Archivo carries the whole display+body weight range (400-900) so scale
// contrast comes from size/weight, not family-mixing. IBM Plex Mono is the
// "data register" face: citation index numerals, eyebrow labels, domain
// badges, score percentages. Both expose a CSS variable that globals.css
// wires into --font-sans / --font-mono, rather than being applied inline,
// so every component keeps drawing from the token layer.
const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-archivo",
  weight: ["400", "500", "600", "700", "800", "900"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Literature Review RAG POC",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${archivo.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
