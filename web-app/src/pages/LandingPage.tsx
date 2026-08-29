import { FC, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Globe,
  HandCoins,
  Landmark,
  Menu,
  Quote,
  ShieldCheck,
  Smartphone,
  Sprout,
  Users,
  X,
} from "lucide-react";
import Reveal from "@/components/landing/Reveal";
import Counter from "@/components/landing/Counter";
import { SYSTEM_NAME, SYSTEM_TAGLINE, CURRENT_YEAR, LOGO_URL } from "@/lib/system";
import LoginSvg from "@/assets/authenticate.svg";
import AitelLogo from "@/assets/aitellogo.jpg";
import CrdbLogo from "@/assets/crdblogo.jpg";
import HaloPesaLogo from "@/assets/halopesalogo.jpg";
import MixxLogo from "@/assets/mixxbyyaslogo.jpg";
import MpesaLogo from "@/assets/mpesalogo.jpg";
import NmbLogo from "@/assets/nmblogo.jpg";
import { detectInstalledApp } from "@/hooks/usePwaStatus";

const navLinks = [
  { href: "#vision", label: `Vision ${CURRENT_YEAR}` },
  { href: "#how", label: "How it works" },
  { href: "#features", label: "Features" },
];

const stats = [
  { to: CURRENT_YEAR, suffix: "", label: "The year we designed for" },
  { to: 2.4, suffix: "M", label: `Members by ${CURRENT_YEAR}`, decimals: 1 },
  { to: 100, suffix: "%", label: "Member-owned" },
  { to: 10, suffix: "+", label: "Languages spoken" },
];

const trustedBrands = [
  { name: "M-Pesa", src: MpesaLogo },
  { name: "NMB", src: NmbLogo },
  { name: "CRDB", src: CrdbLogo },
  { name: "Mixx by Yas", src: MixxLogo },
  { name: "HaloPesa", src: HaloPesaLogo },
  { name: "Aitel", src: AitelLogo },
];

const steps = [
  {
    n: "01",
    icon: <Users className="h-6 w-6" />,
    title: "Form a circle",
    body: "A handful of neighbours agree to meet, contribute, and look out for one another. No institution required.",
  },
  {
    n: "02",
    icon: <HandCoins className="h-6 w-6" />,
    title: "Save & lend",
    body: "Contributions and loans are recorded in the open. Members decide who borrows, and on what terms.",
  },
  {
    n: "03",
    icon: <Sprout className="h-6 w-6" />,
    title: "Grow together",
    body: "Interest returns to the circle. Over time the group funds its own schools, harvests, and emergencies.",
  },
];

const features = [
  { icon: <Landmark />, t: "Savings circles", d: "Track contributions, shares, and payouts without spreadsheets." },
  { icon: <HandCoins />, t: "Fair loans", d: "Members set the rates. Interest stays inside the group." },
  { icon: <Users />, t: "Cooperative governance", d: "Decisions are made in the meeting, not in a faraway office." },
  { icon: <ShieldCheck />, t: "Radical transparency", d: "Every entry is visible to every member. No hidden rows." },
  { icon: <Smartphone />, t: "Mobile-first", d: "Built for the phone in your pocket, on the network you have." },
  { icon: <Globe />, t: "Speaks your language", d: "From Kiswahili to Chinese — the app meets you halfway." },
];

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const LandingPage: FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const deferredPrompt = useRef<InstallPromptEvent | null>(null);

  useEffect(() => {
    const onPrompt = (event: Event) => {
      event.preventDefault();
      deferredPrompt.current = event as InstallPromptEvent;
    };
    const onInstalled = () => {
      deferredPrompt.current = null;
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  // "Open the app": scan for an installed Vikoba PWA first. If it is present,
  // open it at the sign-in page; otherwise raise the one-tap install prompt
  // (when the browser supports it) and continue to the sign-in page.
  const handleOpenApp = async () => {
    const present = await detectInstalledApp();
    if (present) {
      window.location.assign("/login");
      return;
    }
    if (deferredPrompt.current) {
      try {
        await deferredPrompt.current.prompt();
      } catch {
        /* prompt interrupted — continue in the browser */
      }
      deferredPrompt.current = null;
    }
    window.location.assign("/login");
  };

  useEffect(() => {
    document.title = `${SYSTEM_NAME} — ${CURRENT_YEAR}`;
  }, []);

  return (
    <div className="min-h-screen bg-paper font-sans text-ink">
      {/* NAV */}
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <Link to="/" className="flex items-center gap-2.5">
            <img
              src={LOGO_URL}
              alt={`${SYSTEM_NAME} logo`}
              className="h-9 w-9 rounded-xl bg-blue-800/5 p-1"
            />
            <span className="font-display text-xl font-semibold tracking-tight">
              {SYSTEM_NAME}
            </span>
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            {navLinks.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="text-sm font-medium text-slate-600 transition hover:text-blue-800"
              >
                {l.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="hidden text-sm font-medium text-blue-700 hover:underline lg:inline"
            >
              Sign in
            </Link>
            <button
              type="button"
              onClick={handleOpenApp}
              className="inline-flex items-center justify-center rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-soft transition hover:bg-blue-800 lg:hidden"
            >
              Open the app
            </button>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="rounded-lg border border-slate-300 p-2 md:hidden"
              aria-label="Toggle menu"
            >
              {menuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="border-t border-slate-200 bg-paper px-5 py-4 md:hidden">
            <div className="flex flex-col gap-3">
              {navLinks.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  onClick={() => setMenuOpen(false)}
                  className="text-sm font-medium text-slate-700"
                >
                  {l.label}
                </a>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* HERO */}
      <section className="bg-blue-800 text-white">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 lg:grid-cols-2">
          <div>
            <img
              src={LOGO_URL}
              alt={`${SYSTEM_NAME} logo`}
              className="h-12 w-12 rounded-xl bg-white/10 p-1"
            />
            <p className="mt-6 text-xs font-semibold uppercase tracking-[0.18em] text-blue-200">
              A cooperative for the year {CURRENT_YEAR}
            </p>
            <h1 className="mt-3 font-display text-4xl font-semibold leading-tight md:text-5xl">
              Banking, returned to the community.
            </h1>
            <p className="mt-5 max-w-lg text-blue-100/90">
              {SYSTEM_NAME} is savings and credit, rebuilt for the villages and
              towns of {CURRENT_YEAR} — owned by its members, written in your language, and
              honest by design.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to="/login"
                className="hidden items-center gap-2 rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-blue-800 shadow-soft transition hover:bg-blue-50 lg:inline-flex"
              >
                Sign in
              </Link>
              <button
                type="button"
                onClick={handleOpenApp}
                className="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-blue-800 shadow-soft transition hover:bg-blue-50 lg:hidden"
              >
                Open the app
                <ArrowRight size={16} />
              </button>
              <a
                href="#vision"
                className="inline-flex items-center gap-2 rounded-lg border border-white/30 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Read the {CURRENT_YEAR} vision
              </a>
            </div>
          </div>
          <div className="hidden justify-center lg:flex">
            <img src={LoginSvg} alt="" className="w-72 opacity-90" />
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
          {stats.map((s, i) => (
            <Reveal key={s.label} delay={i * 80}>
              <div className="rounded-3xl border border-slate-200 bg-white p-6 text-center shadow-card">
                <p className="font-display text-4xl font-semibold text-blue-800">
                  <Counter to={s.to} suffix={s.suffix} decimals={s.decimals ?? 0} />
                </p>
                <p className="mt-2 text-sm text-slate-500">{s.label}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* TRUSTED BY */}
      <section className="mx-auto max-w-6xl px-5 py-6 md:py-10">
        <Reveal>
          <div className="rounded-[28px] border border-slate-200 bg-white/90 p-6 shadow-card md:p-8">
            <div className="flex flex-col items-center gap-2 text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                Trusted by the ecosystem
              </p>
              <h2 className="font-display text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
                Built for the way communities move money
              </h2>
            </div>

            <div className="mt-7 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {trustedBrands.map((brand, i) => (
                <Reveal key={brand.name} delay={i * 60}>
                  <div className="group flex h-28 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-blue-300 hover:bg-white hover:shadow-md">
                    <img
                      src={brand.src}
                      alt={`${brand.name} logo`}
                      className="max-h-12 w-full object-contain grayscale transition duration-300 group-hover:grayscale-0 sm:max-h-14"
                    />
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* VISION */}
      <section id="vision" className="mx-auto max-w-4xl px-5 py-12">
        <Reveal>
          <div className="rounded-3xl bg-blue-800 p-10 text-white shadow-card">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-200">
              The {CURRENT_YEAR} vision
            </p>
            <h2 className="mt-4 font-display text-3xl font-semibold leading-snug md:text-4xl">
              We didn’t build another bank. We built the one our grandparents
              would recognise, and our grandchildren will trust.
            </h2>
            <p className="mt-5 text-blue-100/90">
              A vikoba is a small circle of people who save together and lend to
              one another. For decades it ran on notebooks and trust. We kept the
              trust, and gave it a calm, honest home on every phone — so the
              group’s money stays the group’s money.
            </p>
          </div>
        </Reveal>
      </section>

      {/* TRUSTED BRANDS */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <Reveal>
          <div className="overflow-hidden rounded-3xl bg-blue-800 p-8 text-white shadow-card md:p-12">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-200">
              Payments you already trust
            </p>
            <div className="mt-4 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              <h2 className="font-display text-3xl font-semibold leading-snug md:text-4xl">
                Where the money moves — on rails you already know.
              </h2>
              <p className="max-w-sm text-sm text-blue-100/90">
                Contributions and payouts ride on familiar, trusted brands, so a
                vikoba feels less like software and more like the group purse it
                always was.
              </p>
            </div>

            <div className="mt-10 grid gap-5 sm:grid-cols-2">
              {[
                {
                  logo: MpesaLogo,
                  name: "M-Pesa",
                  note: "Round up contributions straight from the phone in your pocket.",
                },
                {
                  logo: NmbLogo,
                  name: "NMB Bank",
                  note: "Trusted bank rails for group withdrawals, payouts, and records.",
                },
              ].map((b) => (
                <div
                  key={b.name}
                  className="flex h-full items-center gap-5 rounded-3xl bg-white p-6 shadow-soft"
                >
                  <span className="flex h-24 w-40 shrink-0 items-center justify-center rounded-2xl border border-slate-100 bg-white p-3">
                    <img
                      src={b.logo}
                      alt={`${b.name} logo`}
                      className="max-h-16 w-auto object-contain"
                    />
                  </span>
                  <div>
                    <p className="font-display text-lg font-semibold text-ink">
                      {b.name}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">{b.note}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="mx-auto max-w-6xl px-5 py-16">
        <Reveal>
          <h2 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">
            How a circle works
          </h2>
          <p className="mt-3 max-w-xl text-slate-500">
            Three steps, the same as it has always been — only now it fits in your pocket.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {steps.map((s, i) => (
            <Reveal key={s.n} delay={i * 90}>
              <div className="h-full rounded-3xl border border-slate-200 bg-white p-7 shadow-card">
                <div className="mb-5 flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-800 text-white">
                    {s.icon}
                  </span>
                  <span className="font-display text-lg font-semibold text-blue-800">
                    {s.n}
                  </span>
                </div>
                <h3 className="font-display text-xl font-semibold">{s.title}</h3>
                <p className="mt-2 text-slate-600">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="mx-auto max-w-6xl px-5 py-16">
        <Reveal>
          <h2 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">
            Made to feel human
          </h2>
          <p className="mt-3 max-w-xl text-slate-500">
            Quiet, legible tools for the people who actually use them.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <Reveal key={f.t} delay={i * 60}>
              <div className="group h-full rounded-3xl border border-slate-200 bg-white p-6 shadow-card transition hover:border-blue-400">
                <span className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-800/10 text-blue-800">
                  {f.icon}
                </span>
                <h3 className="font-display text-lg font-semibold">{f.t}</h3>
                <p className="mt-1.5 text-sm text-slate-600">{f.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* QUOTE */}
      <section className="mx-auto max-w-3xl px-5 py-16 text-center">
        <Reveal>
          <Quote className="mx-auto mb-6 h-10 w-10 text-blue-800" />
          <p className="font-display text-2xl font-medium leading-snug md:text-3xl">
            “Before, our savings lived in someone’s notebook. Now they live where
            the whole circle can see them — and nothing changed about who we are.”
          </p>
          <p className="mt-6 text-sm font-semibold uppercase tracking-widest text-slate-400">
            A vikoba chairperson, {CURRENT_YEAR}
          </p>
        </Reveal>
      </section>

      {/* FINAL CTA */}
      <section className="bg-blue-800 text-white">
        <div className="mx-auto max-w-3xl px-5 py-20 text-center">
          <Reveal>
            <h2 className="font-display text-3xl font-semibold md:text-5xl">
              Come build the cooperative economy.
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-blue-100/90">
              {SYSTEM_TAGLINE}.
            </p>
            <Link
              to="/login"
              className="mt-8 hidden items-center gap-2 rounded-lg bg-white px-6 py-3 text-sm font-semibold text-blue-800 shadow-soft transition hover:bg-blue-50 lg:inline-flex"
            >
              Sign in
            </Link>
            <button
              type="button"
              onClick={handleOpenApp}
              className="mt-8 inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3 text-sm font-semibold text-blue-800 shadow-soft transition hover:bg-blue-50 lg:mt-8 lg:hidden"
            >
              Open the app
              <ArrowRight size={16} />
            </button>
          </Reveal>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-slate-200 bg-white py-10 text-slate-500">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-5 md:flex-row">
          <div className="flex items-center gap-2.5">
            <img
              src={LOGO_URL}
              alt={`${SYSTEM_NAME} logo`}
              className="h-9 w-9 rounded-xl bg-blue-800/5 p-1"
            />
            <span className="font-display text-lg font-semibold text-ink">
              {SYSTEM_NAME}
            </span>
          </div>
          <nav className="flex gap-6 text-sm">
            {navLinks.map((l) => (
              <a key={l.href} href={l.href} className="hover:text-blue-800">
                {l.label}
              </a>
            ))}
            <Link to="/login" className="hover:text-blue-800">
              Sign in
            </Link>
          </nav>
          <p className="text-sm">© {CURRENT_YEAR} — built by humans, for humans.</p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
