import { FC, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Menu, X } from "lucide-react";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import { detectInstalledApp } from "@/hooks/usePwaStatus";

const nav = [
  { href: "#how", label: "How it works" },
  { href: "#members", label: "For members" },
  { href: "#groups", label: "For groups" },
  { href: "#about", label: "About" },
];

const LandingPage: FC = () => {
  const [open, setOpen] = useState(false);
  const deferred = useRef<Event | null>(null);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      deferred.current = e;
    };
    const onInstalled = () => {
      deferred.current = null;
    };
    window.addEventListener("beforeinstallprompt", onPrompt as EventListener);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt as EventListener);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const openApp = async () => {
    if (await detectInstalledApp()) {
      window.location.assign("/login");
      return;
    }
    const p = deferred.current as unknown as { prompt?: () => Promise<void> } | null;
    if (p?.prompt) {
      try {
        await p.prompt();
      } catch {}
      deferred.current = null;
    }
    window.location.assign("/login");
  };

  useEffect(() => {
    document.title = `${SYSTEM_NAME} — VICOBA kidigitali`;
  }, []);

  return (
    <div className="min-h-screen bg-[#FDFBF7] font-sans text-[#1A1A1A] antialiased">
      <style>{`html{scroll-behavior:smooth} section[id]{scroll-margin-top:76px}`}</style>

      {/* HEADER */}
      <header className="sticky top-0 z-50 border-b border-[#E8E2D9] bg-[#FDFBF7]/95 backdrop-blur">
        <div className="mx-auto flex h-[64px] max-w-6xl items-center justify-between gap-4 px-4 sm:px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-8 w-8 rounded-lg" />
            <span className="text-[15px] font-semibold tracking-[-0.02em] text-[#115036]">VICOBA KIDIGITALI</span>
          </Link>
          <nav className="hidden items-center gap-6 lg:flex">
            {nav.map((l) => (
              <a key={l.href} href={l.href} className="text-[13px] font-medium text-[#3D3D3D] hover:text-[#115036]">
                {l.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="hidden text-[13px] font-medium text-[#3D3D3D] hover:text-[#115036] lg:inline">
              Sign in
            </Link>
            <button
              onClick={openApp}
              className="inline-flex h-9 items-center justify-center rounded-full bg-[#115036] px-5 text-[13px] font-semibold text-white hover:bg-[#0e442d]"
            >
              Open the app
            </button>
            <button
              onClick={() => setOpen((v) => !v)}
              aria-label="Menu"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[#E8E2D9] bg-white lg:hidden"
            >
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>
        {open && (
          <div className="border-t border-[#E8E2D9] bg-[#FDFBF7] px-4 py-4 lg:hidden">
            <nav className="flex flex-col gap-1">
              {nav.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-[14px] font-medium text-[#1A1A1A] hover:bg-white"
                >
                  {l.label}
                </a>
              ))}
              <Link to="/login" onClick={() => setOpen(false)} className="rounded-lg px-3 py-2.5 text-[14px] font-medium text-[#1A1A1A] hover:bg-white">
                Sign in
              </Link>
            </nav>
          </div>
        )}
      </header>

      {/* HERO */}
      <section className="mx-auto max-w-6xl px-4 pb-8 pt-6 sm:px-5 sm:pt-10">
        <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-start lg:gap-10">
          <div className="pt-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#115036]">VICOBA · Savings group · Community finance</p>
            <h1 className="mt-3 font-display text-[30px] font-[600] leading-[1.05] tracking-[-0.03em] text-[#1A1A1A] sm:text-[40px] lg:text-[44px]">
              Your VICOBA,
              <br />
              now digital.
            </h1>
            <p className="mt-4 max-w-[36ch] text-[15px] leading-6 text-[#3D3D3D]">
              Manage contributions, loans, repayments and group records — all in one place. Everyone sees what happened.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button onClick={openApp} className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-[#115036] px-6 text-[14px] font-semibold text-white hover:bg-[#0e442d]">
                Open the app <ArrowRight size={16} />
              </button>
              <a href="#how" className="inline-flex h-11 items-center justify-center rounded-full border border-[#E8E2D9] bg-white px-6 text-[14px] font-semibold text-[#1A1A1A] hover:bg-[#F5F0E8]">
                See how it works
              </a>
            </div>
            <p className="mt-3 text-[12px] leading-4 text-[#6B6B6B]">Works on your phone. No new bank account needed.</p>
          </div>

          {/* PRODUCT PREVIEW */}
          <div className="relative">
            <div className="overflow-hidden rounded-[20px] border border-[#E8E2D9] bg-white shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
              <div className="flex items-center justify-between border-b border-[#F0EBE0] px-4 py-3">
                <div className="flex items-center gap-2">
                  <img src={LOGO_URL} alt="" className="h-6 w-6 rounded-md" />
                  <span className="text-[12px] font-semibold tracking-[0.04em] text-[#115036]">VICOBA YANGU</span>
                </div>
                <span className="rounded-full bg-[#EEF6F0] px-2.5 py-1 text-[11px] font-semibold text-[#115036]">Active</span>
              </div>

              <div className="p-4">
                <div className="rounded-2xl bg-[#115036] p-4 text-white">
                  <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/70">Balance</p>
                  <p className="mt-1 font-display text-[28px] font-semibold leading-none">TZS 485,000</p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-white/10 px-3 py-2.5">
                      <p className="text-[11px] text-white/70">This month · Contribution</p>
                      <p className="mt-1 text-[14px] font-semibold">TZS 50,000</p>
                    </div>
                    <div className="rounded-xl bg-white/10 px-3 py-2.5">
                      <p className="text-[11px] text-white/70">Loan</p>
                      <p className="mt-1 text-[14px] font-semibold">TZS 300,000</p>
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-[#F0EBE0] bg-[#FDFBF7] px-3 py-3">
                    <p className="text-[11px] font-medium text-[#6B6B6B]">Next contribution</p>
                    <p className="mt-1 text-[13px] font-semibold text-[#1A1A1A]">Friday · 12 Dec</p>
                    <p className="text-[11px] text-[#6B6B6B]">Group meeting 16:00</p>
                  </div>
                  <div className="rounded-xl border border-[#F0EBE0] bg-white px-3 py-3">
                    <p className="text-[11px] font-medium text-[#6B6B6B]">Loan status</p>
                    <p className="mt-1 inline-flex rounded-full bg-[#EEF6F0] px-2 py-0.5 text-[11px] font-semibold text-[#115036]">On track</p>
                    <p className="mt-1 text-[11px] text-[#6B6B6B]">TZS 75,000 due 28 Dec</p>
                  </div>
                </div>

                <div className="mt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#6B6B6B]">Recent activity</p>
                  <div className="mt-2 divide-y divide-[#F0EBE0] overflow-hidden rounded-xl border border-[#F0EBE0]">
                    <div className="flex items-center justify-between bg-white px-3 py-2.5">
                      <div>
                        <p className="text-[13px] font-medium leading-none">Contribution received</p>
                        <p className="text-[11px] text-[#6B6B6B]">12 Dec · Ref #VK-4821</p>
                      </div>
                      <span className="text-[13px] font-semibold text-[#115036]">+50,000</span>
                    </div>
                    <div className="flex items-center justify-between bg-white px-3 py-2.5">
                      <div>
                        <p className="text-[13px] font-medium leading-none">Loan repayment</p>
                        <p className="text-[11px] text-[#6B6B6B]">05 Dec · Approved</p>
                      </div>
                      <span className="text-[13px] font-semibold">-25,000</span>
                    </div>
                    <div className="flex items-center justify-between bg-white px-3 py-2.5">
                      <div>
                        <p className="text-[13px] font-medium leading-none">Withdrawal approved</p>
                        <p className="text-[11px] text-[#6B6B6B]">02 Dec · Disbursed</p>
                      </div>
                      <span className="text-[13px] font-semibold">-80,000</span>
                    </div>
                  </div>
                  <p className="mt-2 text-center text-[11px] text-[#6B6B6B]">Example interface — values are illustrative</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CAPABILITIES - replaces fake stats */}
      <section className="mx-auto max-w-6xl px-4 sm:px-5">
        <div className="grid grid-cols-2 gap-3 border-y border-[#E8E2D9] py-6 sm:grid-cols-4">
          {[
            ["Members", "Know your position"],
            ["Groups", "Same record for all"],
            ["Transactions", "Every movement traceable"],
            ["Access", "On your phone"],
          ].map(([k, v]) => (
            <div key={k} className="px-1">
              <p className="text-[13px] font-semibold text-[#1A1A1A]">{k}</p>
              <p className="text-[12px] leading-4 text-[#6B6B6B]">{v}</p>
            </div>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="mx-auto max-w-6xl px-4 py-12 sm:px-5 sm:py-16">
        <div className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#115036]">How it works</p>
          <h2 className="mt-2 font-display text-[24px] font-semibold leading-tight tracking-[-0.02em] sm:text-[28px]">Four steps, same as always.</h2>
          <p className="mt-2 text-[14px] leading-6 text-[#3D3D3D]">VICOBA has always been four actions. We keep them in one place.</p>
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { n: "01", t: "Create or join your VICOBA", d: "Chairperson creates the group. Members join by invitation. Everyone starts with the same rules." },
            { n: "02", t: "Contribute regularly", d: "Weekly or monthly contributions. Each payment is recorded with a reference anyone can check." },
            { n: "03", t: "Manage and track loans", d: "Request, review, approve and disburse — all with a clear approval trail." },
            { n: "04", t: "See every transaction clearly", d: "Contributions, repayments, withdrawals. Member and group history stays readable." },
          ].map((s) => (
            <div key={s.n} className="rounded-2xl border border-[#E8E2D9] bg-white p-5">
              <p className="text-[11px] font-semibold tracking-[0.1em] text-[#115036]">{s.n}</p>
              <h3 className="mt-2 text-[15px] font-semibold leading-5">{s.t}</h3>
              <p className="mt-2 text-[13px] leading-5 text-[#3D3D3D]">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FOR MEMBERS */}
      <section id="members" className="bg-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:px-5 sm:py-16 lg:grid-cols-2 lg:items-start">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#115036]">For members</p>
            <h2 className="mt-2 font-display text-[24px] font-semibold leading-tight sm:text-[28px]">Everything a member needs to stay informed.</h2>
            <ul className="mt-6 space-y-3">
              {[
                "View contributions",
                "Track savings and hisa",
                "See loan balance",
                "Track repayments",
                "View transaction history",
                "Receive group updates",
                "See personal financial records",
              ].map((t) => (
                <li key={t} className="flex gap-2 text-[14px] leading-5 text-[#1A1A1A]">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#EEF6F0] text-[#115036]">
                    <Check size={12} />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-[#E8E2D9] bg-[#FDFBF7] p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#6B6B6B]">Member view — example</p>
            <div className="mt-3 overflow-hidden rounded-xl border border-[#E8E2D9] bg-white">
              <div className="flex justify-between border-b border-[#F0EBE0] px-4 py-3">
                <span className="text-[12px] font-medium text-[#6B6B6B]">Savings</span>
                <span className="text-[13px] font-semibold">TZS 620,000</span>
              </div>
              <div className="divide-y divide-[#F0EBE0]">
                <div className="flex justify-between px-4 py-3 text-[13px]">
                  <span className="text-[#6B6B6B]">Hisa owned</span>
                  <span className="font-medium">18</span>
                </div>
                <div className="flex justify-between px-4 py-3 text-[13px]">
                  <span className="text-[#6B6B6B]">Loan to repay</span>
                  <span className="font-medium">TZS 225,000</span>
                </div>
                <div className="flex justify-between px-4 py-3 text-[13px]">
                  <span className="text-[#6B6B6B]">Next due</span>
                  <span className="font-medium">28 Dec · TZS 25,000</span>
                </div>
              </div>
              <div className="bg-[#FDFBF7] px-4 py-2.5 text-center text-[11px] text-[#6B6B6B]">History is kept per member, not just per group</div>
            </div>
          </div>
        </div>
      </section>

      {/* FOR GROUPS */}
      <section id="groups" className="mx-auto max-w-6xl px-4 py-12 sm:px-5 sm:py-16">
        <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
          <div className="order-2 lg:order-1">
            <div className="overflow-hidden rounded-2xl border border-[#E8E2D9] bg-white">
              <div className="border-b border-[#F0EBE0] bg-[#FDFBF7] px-4 py-3">
                <p className="text-[12px] font-semibold">Group ledger — example</p>
                <p className="text-[11px] text-[#6B6B6B]">Juhudi VICOBA · 24 members</p>
              </div>
              <div className="divide-y divide-[#F0EBE0] text-[13px]">
                <div className="flex items-center justify-between px-4 py-3">
                  <span className="font-medium">Member management</span>
                  <span className="text-[11px] font-medium text-[#115036]">24 active</span>
                </div>
                <div className="flex items-center justify-between px-4 py-3">
                  <span>Contributions — Dec</span>
                  <span className="font-medium">18 / 24 received</span>
                </div>
                <div className="flex items-center justify-between px-4 py-3">
                  <span>Loan requests</span>
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">2 pending review</span>
                </div>
                <div className="flex items-center justify-between px-4 py-3">
                  <span>Repayments this month</span>
                  <span className="font-medium">TZS 420,000</span>
                </div>
                <div className="flex items-center justify-between px-4 py-3">
                  <span>Withdrawals</span>
                  <span className="text-[11px] text-[#6B6B6B]">Approved → Disbursed</span>
                </div>
                <div className="flex items-center justify-between bg-[#FDFBF7] px-4 py-3">
                  <span className="font-medium">Group ledger</span>
                  <span className="text-[11px] text-[#115036]">Export · Reports</span>
                </div>
              </div>
            </div>
          </div>
          <div className="order-1 lg:order-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#115036]">For groups</p>
            <h2 className="mt-2 font-display text-[24px] font-semibold leading-tight sm:text-[28px]">Run the group without losing track of the numbers.</h2>
            <p className="mt-3 text-[14px] leading-6 text-[#3D3D3D]">This is a group system first. Leaders keep the same book everyone else sees.</p>
            <ul className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {[
                "Member management",
                "Contributions",
                "Loan requests & approvals",
                "Repayments",
                "Withdrawals",
                "Group ledger & history",
                "Financial reports",
                "Transaction history",
              ].map((t) => (
                <li key={t} className="flex gap-2 text-[13px] leading-5">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#115036]" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* TRANSPARENCY */}
      <section className="bg-[#115036] text-white">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-5 sm:py-16">
          <div className="max-w-3xl">
            <h2 className="font-display text-[22px] font-semibold leading-tight sm:text-[28px]">Every contribution. Every repayment. Every withdrawal.</h2>
            <p className="mt-3 max-w-2xl text-[14px] leading-6 text-white/80">VICOBA depends on trust. Records are kept per member and per group — with status, references and history you can follow without asking for the book.</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-white/10 px-4 py-3">
                <p className="text-[13px] font-semibold">Clear records</p>
                <p className="text-[12px] text-white/70">Date, amount, reference</p>
              </div>
              <div className="rounded-xl bg-white/10 px-4 py-3">
                <p className="text-[13px] font-semibold">Member & group view</p>
                <p className="text-[12px] text-white/70">Same ledger, two lenses</p>
              </div>
              <div className="rounded-xl bg-white/10 px-4 py-3">
                <p className="text-[13px] font-semibold">Receipts where applicable</p>
                <p className="text-[12px] text-white/70">Traceable references</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* LOANS */}
      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-5 sm:py-16">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#115036]">Loans</p>
        <h2 className="mt-2 max-w-2xl font-display text-[24px] font-semibold leading-tight sm:text-[28px]">VICOBA lending, not instant credit.</h2>
        <div className="mt-8 overflow-x-auto">
          <div className="flex min-w-[640px] items-start gap-2">
            {[
              ["Member requests", "Amount & purpose"],
              ["Group reviews", "Chair / committee"],
              ["Approved", "Terms agreed"],
              ["Disbursed", "To member account"],
              ["Repayment", "Tracked weekly"],
              ["Completed", "Closed & recorded"],
            ].map(([t, s], i) => (
              <div key={t} className="flex flex-1 items-start gap-2">
                <div className="min-w-0 flex-1 rounded-xl border border-[#E8E2D9] bg-white px-3 py-3 text-center">
                  <p className="text-[12px] font-semibold leading-tight">{t}</p>
                  <p className="text-[11px] text-[#6B6B6B]">{s}</p>
                </div>
                {i < 5 && <span className="mt-4 text-[#115036]">→</span>}
              </div>
            ))}
          </div>
        </div>
        <p className="mt-3 text-[11px] text-[#6B6B6B]">No “instant loans”. Every loan follows the group’s process.</p>
      </section>

      {/* WITHDRAWALS */}
      <section className="mx-auto max-w-6xl px-4 pb-12 sm:px-5">
        <div className="rounded-2xl border border-[#E8E2D9] bg-white p-5 sm:p-6">
          <h3 className="text-[15px] font-semibold">Controlled withdrawals</h3>
          <p className="mt-1 text-[13px] text-[#3D3D3D]">Withdrawals are requested, reviewed, approved, disbursed and recorded — not automatic.</p>
          <div className="mt-4 flex flex-wrap gap-2 text-[12px]">
            <span className="rounded-full border border-[#E8E2D9] bg-[#FDFBF7] px-3 py-1.5 font-medium">Requested</span>
            <span className="py-1.5 text-[#6B6B6B]">→</span>
            <span className="rounded-full border border-[#E8E2D9] bg-[#FDFBF7] px-3 py-1.5 font-medium">Review</span>
            <span className="py-1.5 text-[#6B6B6B]">→</span>
            <span className="rounded-full border border-[#E8E2D9] bg-[#FDFBF7] px-3 py-1.5 font-medium">Approved</span>
            <span className="py-1.5 text-[#6B6B6B]">→</span>
            <span className="rounded-full bg-[#115036] px-3 py-1.5 font-semibold text-white">Disbursed & recorded</span>
          </div>
        </div>
      </section>

      {/* PAYMENTS - only if true, keep modest */}
      <section className="mx-auto max-w-6xl px-4 pb-12 sm:px-5">
        <div className="rounded-2xl bg-[#FDFBF7] p-5 sm:p-6">
          <h3 className="text-[15px] font-semibold">Contribute and keep the record connected</h3>
          <p className="mt-1 max-w-2xl text-[13px] leading-5 text-[#3D3D3D]">When you contribute, the payment record stays linked to your VICOBA account — so the group and the member see the same entry. If mobile-money is used by your group, the reference is kept with the transaction.</p>
        </div>
      </section>

      {/* TRUST */}
      <section className="mx-auto max-w-6xl px-4 pb-12 sm:px-5">
        <h2 className="font-display text-[20px] font-semibold">Built to be trusted because it is clear</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Clear records", "Every action has a readable entry."],
            ["Member visibility", "Each member sees their own history."],
            ["Controlled approvals", "Loans and withdrawals follow group decisions."],
            ["Transaction history", "Group and member ledgers stay aligned."],
            ["Account access", "Sign in to view your data."],
            ["Responsible data handling", "Financial data treated with care."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-xl border border-[#E8E2D9] bg-white px-4 py-3">
              <p className="text-[13px] font-semibold">{t}</p>
              <p className="text-[12px] text-[#6B6B6B]">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ABOUT */}
      <section id="about" className="mx-auto max-w-3xl px-4 py-12 sm:px-5">
        <div className="rounded-2xl border border-[#E8E2D9] bg-white p-6 sm:p-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#115036]">About</p>
          <h2 className="mt-2 font-display text-[22px] font-semibold leading-tight">Community savings, kept where it belongs.</h2>
          <p className="mt-3 text-[14px] leading-6 text-[#3D3D3D]">
            For years VICOBA has run on notebooks and trust. We keep the trust and give it a place on every phone — so contributions, loans and records stay with the group, and everyone can follow them.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[#115036] text-white">
        <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-5">
          <h2 className="font-display text-[26px] font-semibold leading-tight sm:text-[32px]">Ready to bring your VICOBA onto your phone?</h2>
          <p className="mx-auto mt-3 max-w-xl text-[14px] leading-6 text-white/80">Keep contributions, loans and group records in one place.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button onClick={openApp} className="inline-flex h-11 items-center justify-center rounded-full bg-white px-6 text-[14px] font-semibold text-[#115036] hover:bg-[#F5F0E8]">
              Open the app
            </button>
            <Link to="/groups" className="inline-flex h-11 items-center justify-center rounded-full border border-white/30 px-6 text-[14px] font-semibold text-white hover:bg-white/10">
              Start a group
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-[#E8E2D9] bg-white">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-5">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <div className="flex items-center gap-2">
                <img src={LOGO_URL} alt="" className="h-8 w-8 rounded-lg" />
                <span className="text-[15px] font-semibold tracking-[-0.02em] text-[#115036]">VICOBA KIDIGITALI</span>
              </div>
              <p className="mt-3 max-w-sm text-[13px] leading-5 text-[#3D3D3D]">Savings and credit for VICOBA groups — contributions, loans and records in one place.</p>
            </div>
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#1A1A1A]">Product</p>
              <div className="mt-3 flex flex-col gap-2 text-[13px] text-[#3D3D3D]">
                <a href="#how" className="hover:text-[#115036]">How it works</a>
                <a href="#members" className="hover:text-[#115036]">Members</a>
                <a href="#groups" className="hover:text-[#115036]">Groups</a>
              </div>
            </div>
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#1A1A1A]">Company</p>
              <div className="mt-3 flex flex-col gap-2 text-[13px] text-[#3D3D3D]">
                <a href="#about" className="hover:text-[#115036]">About</a>
                <Link to="/help" className="hover:text-[#115036]">Contact</Link>
              </div>
            </div>
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#1A1A1A]">Legal</p>
              <div className="mt-3 flex flex-col gap-2 text-[13px] text-[#3D3D3D]">
                <Link to="/help" className="hover:text-[#115036]">Privacy</Link>
                <Link to="/help" className="hover:text-[#115036]">Terms</Link>
              </div>
              <p className="mt-4 text-[12px] font-semibold uppercase tracking-[0.08em] text-[#1A1A1A]">App</p>
              <button onClick={openApp} className="mt-1 text-[13px] font-medium text-[#115036] hover:underline">
                Open the app
              </button>
            </div>
          </div>
          <div className="mt-8 flex flex-col gap-2 border-t border-[#F0EBE0] pt-6 text-[12px] text-[#6B6B6B] sm:flex-row sm:items-center sm:justify-between">
            <span>© {new Date().getFullYear()} VICOBA KIDIGITALI</span>
            <span className="text-[11px]">English · Tanzania</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
