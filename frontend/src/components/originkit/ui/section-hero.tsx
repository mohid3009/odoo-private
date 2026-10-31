/* eslint-disable */
// @ts-nocheck
"use client";
import React from "react";
import DitherReveal from "@/components/originkit/ui/dither-reveal";
import "./hero-40.css";

const navigation = [
  { label: "Problem", href: "#problem" },
  { label: "Solution", href: "#solution" },
  { label: "Features", href: "#features" },
  { label: "Who It's For", href: "#roles" },
  { label: "Impact", href: "#impact" },
];

export function SectionHero() {
  return (
    <div className="hero-40">
      <main className="landing">
        <section className="hero" id="home">
          <div className="noise" aria-hidden="true" />

          <div className="dither-layer" aria-hidden="true">
            <DitherReveal
              image={{
                src: "/sections/hero-40/assets/white-hands.png",
                alt: "Two polished liquid chrome hands reaching toward each other with Bayer halftone dither reveal",
              }}
              wave={true}
              waveSpeed={55}
              waveDensity={22}
              revealRadius={190}
              revealSoftness={45}
              dotSize={5}
            />
          </div>

          <header className="site-header">
            <a className="brand" href="/" aria-label="Brightloop home">
              <span className="brand-dot" />
              Brightloop
            </a>

            <nav className="desktop-nav" aria-label="Primary navigation">
              {navigation.map((item) => (
                <a key={item.label} href={item.href}>
                  {item.label}
                </a>
              ))}
            </nav>

            <a className="header-cta" href="/login">
              Log in
              <span aria-hidden="true">↗</span>
            </a>
          </header>

          <section className="hero-content" aria-labelledby="hero-title">
            <p className="eyebrow">SUBSCRIPTION BILLING PLATFORM</p>
            <h1 id="hero-title">
              <span className="headline-line headline-line-muted">Run Recurring Revenue</span>
              <span className="headline-line">Without The Spreadsheets</span>
            </h1>
            <p className="hero-copy">
              From quote to payment, Brightloop plans, bills and tracks every subscription automatically,
              so renewals are never missed and invoices are never wrong.
            </p>
            <a className="primary-cta" href="/login" id="journey">
              Log in
              <span aria-hidden="true">↗</span>
            </a>
          </section>

          <footer className="hero-footer">
            <p>Every subscription, billed on time.</p>
            <a className="scroll-cue" href="#problem">
              scroll <span aria-hidden="true">↓</span>
            </a>
            <p>
              Plans, invoices and payments
              <br /> in one place for growing software companies.
            </p>
          </footer>
        </section>
      </main>
    </div>
  );
}

export default SectionHero;

