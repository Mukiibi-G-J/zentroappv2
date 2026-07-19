'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { motion, useInView, useReducedMotion, AnimatePresence } from 'framer-motion'
import { HOME_FAQ } from '@/config/seo.config'
import {
  getAddOns,
  getPricingPlansLanding,
  sendContactEmail,
} from '@/services/marketingServices'
import { PlanComparisonTable } from '@/components/pricing/PlanComparisonTable'
import { AddOnsSection } from '@/components/pricing/AddOnsSection'
import { MobileAppDownload } from '@/components/marketing/MobileAppDownload'
import { DesktopAppDownload } from '@/components/marketing/DesktopAppDownload'
import { ANDROID_APK_DOWNLOAD_URL } from '@/constants/mobileApp'
import { DESKTOP_WINDOWS_DOWNLOAD_URL } from '@/constants/desktopApp'
import { ProductScrollShowcase } from '@/components/marketing/ProductScrollShowcase'
import {
  BackgroundPathsLayer,
  AnimatedGradientTitle,
} from '@/components/ui/background-paths'
import type { AddOn, PlanComparisonPlan } from '@/types/pricing'
import {
  FaBoxOpen,
  FaReceipt,
  FaChartLine,
  FaCheckCircle,
  FaCheck,
  FaEnvelope,
  FaPhone,
  FaMapMarkerAlt,
  FaBolt,
  FaCrown,
  FaArrowRight,
  FaStar,
  FaCashRegister,
  FaCodeBranch,
  FaMobileAlt,
  FaWhatsapp,
  FaBars,
  FaTimes,
  FaQuoteLeft,
} from 'react-icons/fa'

const LOGO_WHITE = '/img/logo/logo-white.png'
const LOGO_LIGHT = '/img/logo/logo-light-full.png'
const isDevelopment = process.env.NODE_ENV === 'development'

// ─── Animation helpers ────────────────────────────────────────────────────────

function FadeUp({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const reduced = useReducedMotion();

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={reduced ? {} : { opacity: 0, y: 24 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function StaggerContainer({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const reduced = useReducedMotion();

  return (
    <motion.div
      ref={ref}
      className={className}
      initial="hidden"
      animate={inView ? "show" : "hidden"}
      variants={
        reduced
          ? {}
          : {
              hidden: {},
              show: { transition: { staggerChildren: 0.1 } },
            }
      }
    >
      {children}
    </motion.div>
  );
}

function StaggerItem({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      variants={
        reduced
          ? {}
          : {
              hidden: { opacity: 0, y: 20 },
              show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
            }
      }
    >
      {children}
    </motion.div>
  );
}

// ─── Stat counter ─────────────────────────────────────────────────────────────

function StatCounter({ value, suffix = "", label }: { value: number; suffix?: string; label: string }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const reduced = useReducedMotion();
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!inView || reduced) {
      setCount(value);
      return;
    }
    let start = 0;
    const step = value / 50;
    const timer = setInterval(() => {
      start += step;
      if (start >= value) {
        setCount(value);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 30);
    return () => clearInterval(timer);
  }, [inView, value, reduced]);

  return (
    <div ref={ref} className="text-center">
      <div className="text-4xl lg:text-5xl font-extrabold text-white tabular-nums">
        {count.toLocaleString()}{suffix}
      </div>
      <div className="mt-1 text-blue-200 text-sm font-medium">{label}</div>
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  description,
  dark = false,
  className = "",
}: {
  eyebrow: string;
  title: string;
  description?: string;
  dark?: boolean;
  className?: string;
}) {
  return (
    <FadeUp className={`text-center max-w-2xl mx-auto mb-16 ${className}`}>
      <span
        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold mb-4 uppercase tracking-wide ${
          dark
            ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
            : "bg-blue-600/10 text-blue-700"
        }`}
      >
        {eyebrow}
      </span>
      <h2
        className={`text-4xl sm:text-5xl font-extrabold mb-4 tracking-tight ${
          dark ? "text-white" : "text-gray-900"
        }`}
      >
        {title}
      </h2>
      {description && (
        <p className={`text-lg leading-relaxed ${dark ? "text-blue-100/70" : "text-gray-600"}`}>
          {description}
        </p>
      )}
    </FadeUp>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function LandingPage() {
  const [isYearly, setIsYearly] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [pricingPlans, setPricingPlans] = useState<PlanComparisonPlan[]>([])
  const [addOns, setAddOns] = useState<AddOn[]>([])
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState<string | undefined>(undefined);
  const [contactMessage, setContactMessage] = useState("");
  const [contactSending, setContactSending] = useState(false);
  const [contactSuccess, setContactSuccess] = useState<string | null>(null);
  const [contactError, setContactError] = useState<string | null>(null);
  const [navLight, setNavLight] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const router = useRouter()

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;

    const observer = new IntersectionObserver(
      ([entry]) => setNavLight(!entry.isIntersecting),
      { threshold: 0, rootMargin: "-72px 0px 0px 0px" },
    );
    observer.observe(hero);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const hostname = window.location.hostname;
    const hostParts = hostname.split(".");
    let isSubdomain = false;
    if (isDevelopment) {
      isSubdomain = hostParts.length > 1 && hostParts[1] === "localhost";
    } else {
      isSubdomain =
        hostParts.length > 2 &&
        hostParts[0] !== "www" &&
        hostParts[1] === "zentroapp" &&
        hostParts[2] === "app";
    }
    if (isSubdomain) {
      const domain = isDevelopment
        ? "localhost"
        : process.env.NEXT_PUBLIC_APP_HOST ?? "zentroapp.app";
      // Never treat the API host as the marketing app host
      const safeDomain =
        domain.includes("backend.com") || domain.includes("zentroapp-api")
          ? "zentroapp.app"
          : domain;
      const port = isDevelopment ? ':3000' : ''
      window.location.href = `${window.location.protocol}//${safeDomain}${port}/`;
    }
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [plans, addons] = await Promise.all([
          getPricingPlansLanding(),
          getAddOns(),
        ])
        setPricingPlans(Array.isArray(plans) ? plans : []);
        setAddOns(Array.isArray(addons) ? addons : []);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch pricing data:", err);
        setError("Failed to load pricing plans. Please try again later.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleContactSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setContactSuccess(null);
    setContactError(null);
    if (!contactEmail.trim() || contactMessage.trim().length === 0) {
      setContactError("Email and message are required");
      return;
    }
    try {
      setContactSending(true);
      await sendContactEmail({
        name: contactName,
        email: contactEmail,
        phone: contactPhone,
        message: contactMessage,
      })
      setContactSuccess("Message sent! We'll get back to you shortly.");
      setContactName("");
      setContactEmail("");
      setContactPhone(undefined);
      setContactMessage("");
    } catch (err: any) {
      setContactError("Failed to send message. Please try again.");
      console.error(err);
    } finally {
      setContactSending(false);
    }
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-white" style={{ scrollBehavior: 'smooth' }}>
      {/* ── Navigation ──────────────────────────────────────────────────────── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          navLight
            ? "bg-white/95 backdrop-blur-md shadow-sm border-b border-gray-200/80"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex-shrink-0">
              <img
                className="h-8 w-auto transition-opacity duration-300"
                src={navLight ? LOGO_LIGHT : LOGO_WHITE}
                alt="ZentroApp point of sale Africa logo"
              />
            </div>

            {/* Desktop menu */}
            <div className="hidden md:flex items-center gap-1">
              {["#features", "#how-it-works", "#pricing", "#contact"].map((href, idx) => {
                const labels = ["Features", "How It Works", "Pricing", "Contact"];
                return (
                  <a
                    key={href}
                    href={href}
                    className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer ${
                      navLight ? "text-gray-600 hover:text-gray-900 hover:bg-gray-50" : "text-white/80 hover:text-white hover:bg-white/10"
                    }`}
                  >
                    {labels[idx]}
                  </a>
                );
              })}
            </div>

            <div className="hidden md:flex items-center gap-2">
              <MobileAppDownload variant={navLight ? "nav" : "navDark"} />
              <DesktopAppDownload variant={navLight ? "nav" : "navDark"} />
              <Link
                href="/workspace"
                className={`text-sm font-medium px-4 py-2 rounded-lg border transition-colors cursor-pointer ${
                  navLight
                    ? "border-gray-200 text-gray-700 hover:bg-gray-50"
                    : "border-white/30 text-white hover:bg-white/10"
                }`}
              >
                Log in
              </Link>
              <Link
                href="/signup"
                className="text-sm font-semibold px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm cursor-pointer"
              >
                Start Free Trial
              </Link>
            </div>

            {/* Mobile hamburger */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className={`md:hidden p-2 rounded-lg transition-colors cursor-pointer ${
                navLight ? "text-gray-700 hover:bg-gray-50" : "text-white hover:bg-white/10"
              }`}
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? <FaTimes className="h-5 w-5" /> : <FaBars className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="md:hidden bg-white border-t border-gray-100 overflow-hidden"
            >
              <div className="px-4 py-4 space-y-1">
                {[
                  { href: "#features", label: "Features" },
                  { href: "#how-it-works", label: "How It Works" },
                  { href: "#pricing", label: "Pricing" },
                  { href: "#contact", label: "Contact" },
                ].map(({ href, label }) => (
                  <a
                    key={href}
                    href={href}
                    className="block px-3 py-2.5 text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg font-medium transition-colors cursor-pointer"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {label}
                  </a>
                ))}
                <div className="pt-3 space-y-2 border-t border-gray-100">
                  <MobileAppDownload
                    variant="menu"
                    onNavigate={() => setIsMobileMenuOpen(false)}
                  />
                  <DesktopAppDownload
                    variant="menu"
                    onNavigate={() => setIsMobileMenuOpen(false)}
                  />
                  <Link
                    href="/signup"
                    className="block px-3 py-2.5 text-center bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Start Free Trial
                  </Link>
                  <Link
                    href="/workspace"
                    className="block px-3 py-2.5 text-center border border-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Log in
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <header ref={heroRef} className="relative min-h-screen flex items-center overflow-hidden">
        {/* Background */}
        <div className="absolute inset-0 bg-[#0B1120]" />
        <div className="absolute inset-0">
          <BackgroundPathsLayer />
        </div>
        {/* Gradient orbs */}
        <div className="absolute top-[-10%] left-[-5%] w-[600px] h-[600px] rounded-full opacity-20 pointer-events-none"
          style={{ background: "radial-gradient(circle, #2563EB 0%, transparent 70%)" }} />
        <div className="absolute bottom-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full opacity-[0.15] pointer-events-none"
          style={{ background: "radial-gradient(circle, #7C3AED 0%, transparent 70%)" }} />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-16 w-full">
          <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-16">

            {/* ── Left: copy ── */}
            <div className="flex-1 max-w-2xl">
              {/* Badge */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
              >
                <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 mb-6">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  EFRIS Certified · Built for Africa
                </span>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
                className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-[1.08] tracking-tight mb-6"
              >
                Point of sale software
                <br />
                for African businesses
                <span className="sr-only">, point of sale software in Uganda, EFRIS compliant POS in Kampala and nationwide</span>
              </motion.h1>
              <p className="text-xl sm:text-2xl font-semibold text-blue-200/90 mb-2">
                <AnimatedGradientTitle title="Smarter checkout. Faster growth." />
              </p>

              <motion.p
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                className="text-lg sm:text-xl text-blue-100/70 mb-10 max-w-2xl leading-relaxed"
              >
                ZentroApp is the all-in-one POS and inventory platform trusted by African businesses with built-in EFRIS receipting, multi-branch control, and an Android app that works offline.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
                className="flex flex-col sm:flex-row gap-3 mb-8"
              >
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-500 transition-all duration-200 shadow-lg shadow-blue-600/25 cursor-pointer"
                >
                  Start Free Trial
                  <FaArrowRight className="text-sm" />
                </Link>
                <a
                  href="#features"
                  className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl border border-white/20 text-white font-medium hover:bg-white/10 transition-all duration-200 cursor-pointer"
                >
                  Explore features
                </a>
              </motion.div>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.45 }}
                className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-blue-200/60"
              >
                {["14-day free trial", "No credit card needed", "Free onboarding support"].map((t) => (
                  <span key={t} className="flex items-center gap-1.5">
                    <FaCheck className="text-blue-400 text-xs" />
                    {t}
                  </span>
                ))}
              </motion.div>
            </div>

            {/* ── Right: POS device ── */}
            <HeroDevice />

          </div>
        </div>
      </header>

      {/* ── Stats strip ─────────────────────────────────────────────────────── */}
      <section className="relative border-y border-white/10 bg-[#0B1120] py-16">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(37,99,235,0.08),transparent_70%)]"
        />
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-10 md:divide-x md:divide-white/10">
            <StatCounter value={500} suffix="+" label="Businesses on Zentro" />
            <StatCounter value={99} suffix="%" label="Uptime guaranteed" />
            <StatCounter value={14} label="Days free trial" />
            <StatCounter value={24} suffix="/7" label="Customer support" />
          </div>
        </div>
      </section>

      <ProductScrollShowcase />

      {/* ── Features ────────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 bg-[#F8FAFC]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <SectionHeader
            eyebrow="Why businesses choose Zentro"
            title="EFRIS-compliant POS built for real African businesses"
            description="From a single shop to multi-branch retailers across Africa. Zentro scales with you."
          />

          <StaggerContainer className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <StaggerItem>
              <FeatureCard
                icon={<FaBoxOpen />}
                title="Smart Inventory"
                description="Real-time stock tracking, automated low-stock alerts, and bulk product import, all in one dashboard."
              />
            </StaggerItem>
            <StaggerItem>
              <FeatureCard
                icon={<FaReceipt />}
                title="EFRIS Integration"
                description="Fully certified with Uganda Revenue Authority's Electronic Fiscal Receipting System. Receipts in seconds."
              />
            </StaggerItem>
            <StaggerItem>
              <FeatureCard
                icon={<FaChartLine />}
                title="Sales Analytics"
                description="Daily, weekly, and monthly reports with visual charts. Know your best sellers and peak hours."
              />
            </StaggerItem>
            <StaggerItem>
              <FeatureCard
                icon={<FaCashRegister />}
                title="Fast POS"
                description="Intuitive checkout for any device: barcode scanning, split payments, and customer receipts."
              />
            </StaggerItem>
            <StaggerItem>
              <FeatureCard
                icon={<FaCodeBranch />}
                title="Multi-Branch"
                description="Manage every location from one account. Separate stock, staff, and reports per branch."
              />
            </StaggerItem>
            <StaggerItem>
              <FeatureCard
                icon={<FaMobileAlt />}
                title="Offline Android App"
                description="Keep selling without internet. Your data syncs automatically the moment you reconnect."
              />
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {/* ── Apps callout (mobile + desktop) ─────────────────────────────────── */}
      <section className="py-20 bg-white border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-20">
            <FadeUp className="flex-shrink-0 w-full lg:w-[420px]">
              <img
                src="/image/pos-device-home.jpg"
                alt="ZentroApp mobile POS app, run your business from anywhere"
                className="w-full rounded-3xl shadow-2xl"
                loading="lazy"
              />
            </FadeUp>
            <FadeUp delay={0.15} className="flex-1 max-w-xl">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 mb-5 uppercase tracking-wide">
                Apps
              </span>
              <h2 className="text-4xl sm:text-5xl font-extrabold text-gray-900 tracking-tight mb-6 leading-tight">
                Run your business
                <br />
                <span className="text-blue-600">from anywhere.</span>
              </h2>
              <p className="text-lg text-gray-500 leading-relaxed mb-8">
                Get the Android app for on-the-go sales, or install Zentro Desktop for Windows
                for a full POS workstation with silent printing and offline support.
              </p>
              <div className="flex flex-col gap-6">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
                    Mobile
                  </p>
                  <MobileAppDownload variant="featured" />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
                    Desktop
                  </p>
                  <DesktopAppDownload variant="featured" />
                </div>
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition-colors cursor-pointer w-fit"
                >
                  Start free trial
                  <FaArrowRight className="text-sm" />
                </Link>
              </div>
              <div className="mt-8 flex flex-wrap gap-4">
                {["Offline mode", "EFRIS receipts", "Multi-branch", "Print labels"].map((tag) => (
                  <span key={tag} className="flex items-center gap-1.5 text-sm text-gray-500">
                    <FaCheck className="text-green-500 text-xs" />
                    {tag}
                  </span>
                ))}
              </div>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ── How It Works ────────────────────────────────────────────────────── */}
      <section id="how-it-works" className="relative py-24 overflow-hidden bg-[#0B1120]">
        <div className="absolute inset-0">
          <BackgroundPathsLayer />
        </div>
        <div className="absolute top-[-10%] right-[-5%] w-[400px] h-[400px] rounded-full opacity-20 pointer-events-none"
          style={{ background: "radial-gradient(circle, #2563EB 0%, transparent 70%)" }} />

        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <SectionHeader
            dark
            eyebrow="Setup in minutes"
            title="Retail & restaurant POS: up and running fast"
            description="No IT team. No long onboarding. Issue EFRIS receipts and sell offline when internet drops."
          />

          <StaggerContainer className="grid md:grid-cols-3 gap-6 md:gap-8">
            {[
              {
                step: "01",
                title: "Create your account",
                desc: "Sign up, choose a plan, and set up your company profile in under 5 minutes.",
                icon: <FaCheck />,
              },
              {
                step: "02",
                title: "Add your inventory",
                desc: "Import products via CSV or add them manually. Set prices and stock levels per branch.",
                icon: <FaBoxOpen />,
              },
              {
                step: "03",
                title: "Start selling",
                desc: "Process sales, issue EFRIS receipts, and watch your analytics update in real time.",
                icon: <FaChartLine />,
              },
            ].map(({ step, title, desc, icon }) => (
              <StaggerItem key={step}>
                <div className="relative h-full rounded-2xl border border-white/10 bg-white/5 p-8 backdrop-blur-sm transition-colors hover:bg-white/[0.07]">
                  <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/20 text-lg text-blue-300">
                    {icon}
                  </div>
                  <div className="absolute top-6 right-6 select-none text-5xl font-black leading-none text-white/5">
                    {step}
                  </div>
                  <h3 className="mb-3 text-lg font-bold text-white">{title}</h3>
                  <p className="text-sm leading-relaxed text-blue-100/60">{desc}</p>
                </div>
              </StaggerItem>
            ))}
          </StaggerContainer>

          <FadeUp delay={0.3} className="text-center mt-12">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 px-8 py-3.5 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-500 transition-all duration-200 shadow-lg shadow-blue-600/25 cursor-pointer"
            >
              Get started for free
              <FaArrowRight className="text-sm" />
            </Link>
          </FadeUp>
        </div>
      </section>

      {/* ── Testimonials ────────────────────────────────────────────────────── */}
      <section className="py-24 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <SectionHeader
            eyebrow="Trusted across Africa"
            title="What our customers say"
            description="Real feedback from shop owners, managers, and operators using Zentro every day."
          />

          <StaggerContainer className="grid md:grid-cols-3 gap-6">
            <StaggerItem>
              <TestimonialCard
                quote="ZentroApp replaced 3 different tools for us. Stock control and EFRIS receipts in one place. It's a game changer."
                author="Ronald K."
                role="Retail Shop Owner"
                location="Kampala"
                initials="RK"
                color="blue"
              />
            </StaggerItem>
            <StaggerItem>
              <TestimonialCard
                quote="The multi-branch feature is exactly what we needed. We see all locations in real time from a single dashboard."
                author="Grace M."
                role="Operations Manager"
                location="Mbarara"
                initials="GM"
                color="violet"
              />
            </StaggerItem>
            <StaggerItem>
              <TestimonialCard
                quote="Setup was surprisingly fast. We were processing sales the same day we signed up. Highly recommend."
                author="David O."
                role="Pharmacy Owner"
                location="Entebbe"
                initials="DO"
                color="emerald"
              />
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {/* ── CTA Banner ──────────────────────────────────────────────────────── */}
      <section className="relative py-24 overflow-hidden">
        <div className="absolute inset-0 bg-[#0B1120]" />
        <div className="absolute inset-0">
          <BackgroundPathsLayer />
        </div>
        <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full opacity-20 pointer-events-none"
          style={{ background: "radial-gradient(circle, #2563EB 0%, transparent 70%)" }} />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 rounded-full opacity-15"
          style={{ background: "radial-gradient(circle, #7C3AED 0%, transparent 70%)" }} />
        <FadeUp className="relative z-10 text-center max-w-2xl mx-auto px-4">
          <h2 className="text-4xl sm:text-5xl font-extrabold text-white mb-6 tracking-tight">
            Ready to grow your business?
          </h2>
          <p className="text-blue-200/70 text-lg mb-10">
            Join hundreds of African businesses already running on ZentroApp. Start your 14-day free trial today.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-500 transition-all shadow-lg shadow-blue-600/30 cursor-pointer"
            >
              Start Free Trial
              <FaArrowRight className="text-sm" />
            </Link>
            <a
              href="#contact"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl border border-white/20 text-white font-medium hover:bg-white/10 transition-all cursor-pointer"
            >
              Talk to sales
            </a>
          </div>
        </FadeUp>
      </section>

      {/* ── Pricing ─────────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-24 bg-[#F8FAFC]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <SectionHeader
            eyebrow="Simple, transparent pricing"
            title="Plans that grow with you"
            description="Starting from UGX 50,000/month · 14-day free trial · No large upfront cost"
          />

          <BillingToggle isYearly={isYearly} onChange={setIsYearly} />

          {loading ? (
            <div className="flex justify-center items-center py-16">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-5 py-2.5 rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors cursor-pointer"
              >
                Try Again
              </button>
            </div>
          ) : (
            <>
              <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-8">
                <PlanComparisonTable
                  plans={pricingPlans}
                  isYearly={isYearly}
                  onSelectPlan={() => router.push('/login')}
                  showActions={true}
                  actionHref="/signup"
                />
              </div>

              <AddOnsSection addOns={addOns} />
            </>
          )}

          <FadeUp delay={0.2} className="mt-12 text-center">
            <p className="text-gray-500 mb-5">All plans include 24/7 support, regular updates, and automatic backups</p>
            <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
              {["No hidden fees", "Cancel anytime", "Free setup", "Data backup included"].map((item) => (
                <span key={item} className="flex items-center gap-2 text-sm text-gray-700">
                  <FaCheckCircle className="text-green-500" />
                  {item}
                </span>
              ))}
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ── Contact ─────────────────────────────────────────────────────────── */}
      <section id="contact" className="py-24 bg-white border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <SectionHeader
            eyebrow="Get in touch"
            title="We'd love to hear from you"
            description="Questions, demo requests, or just want to say hello. We respond fast."
          />

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
            {/* Contact info sidebar */}
            <FadeUp className="lg:col-span-2">
              <div className="rounded-2xl p-8 h-full bg-[#0B1120] border border-white/8">
                <h3 className="text-lg font-bold text-white mb-1">Contact information</h3>
                <p className="text-gray-500 text-sm mb-8">Reach us through any of the channels below.</p>
                <div className="space-y-6">
                  <ContactInfoItem icon={<FaEnvelope />} label="Email" value="info@zentroapp.com" />
                  <ContactInfoItem icon={<FaPhone />} label="Phone" value="+256 750 440 865 · +256 798 997 89" />
                  <ContactInfoItem
                    icon={<FaWhatsapp />}
                    label="WhatsApp"
                    value="+256 750 440 865"
                    href="https://wa.me/256750440865"
                  />
                  <ContactInfoItem icon={<FaMapMarkerAlt />} label="Office" value="Ntinda, Kampala, Uganda" />
                </div>

                {/* Bottom accent */}
                <div className="mt-10 pt-6 border-t border-white/8">
                  <p className="text-xs text-gray-600">We typically reply within a few hours on business days.</p>
                </div>
              </div>
            </FadeUp>

            {/* Contact form */}
            <FadeUp delay={0.1} className="lg:col-span-3">
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8">
                <form className="space-y-5" onSubmit={handleContactSubmit}>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <InputField
                      label="Full name"
                      type="text"
                      placeholder="Your name"
                      value={contactName}
                      onChange={(e: any) => setContactName(e.target.value)}
                    />
                    <InputField
                      label="Email address"
                      type="email"
                      placeholder="you@example.com"
                      value={contactEmail}
                      onChange={(e: any) => setContactEmail(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Phone number</label>
                    <input
                      type="tel"
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-sm"
                      placeholder="e.g. +256 750 440 865"
                      value={contactPhone ?? ''}
                      onChange={(e) => setContactPhone(e.target.value || undefined)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Message</label>
                    <textarea
                      rows={4}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none text-sm"
                      placeholder="Tell us how we can help..."
                      value={contactMessage}
                      onChange={(e) => setContactMessage(e.target.value)}
                    />
                  </div>

                  <AnimatePresence>
                    {contactError && (
                      <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                        className="text-red-600 text-sm bg-red-50 px-4 py-2.5 rounded-lg">
                        {contactError}
                      </motion.p>
                    )}
                    {contactSuccess && (
                      <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                        className="text-green-700 text-sm bg-green-50 px-4 py-2.5 rounded-lg flex items-center gap-2">
                        <FaCheckCircle className="text-green-500" />
                        {contactSuccess}
                      </motion.p>
                    )}
                  </AnimatePresence>

                  <button
                    type="submit"
                    disabled={contactSending}
                    className="w-full py-3.5 px-6 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {contactSending ? "Sending…" : "Send Message"}
                  </button>
                </form>
              </div>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ── FAQ (SEO) ───────────────────────────────────────────────────────── */}
      <section id="faq" className="py-24 bg-[#F8FAFC] border-t border-gray-100">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <SectionHeader
            eyebrow="FAQ"
            title="Point of sale & EFRIS questions"
            description="Common questions from shop owners and managers in Uganda and across Africa."
          />
          <FaqAccordion items={HOME_FAQ} />
        </div>
      </section>

      {/* ── East Africa ─────────────────────────────────────────────────────── */}
      <section className="py-16 bg-[#F8FAFC] border-t border-gray-100">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Built for Africa, trusted in Uganda and beyond
          </h2>
          <p className="text-gray-600 leading-relaxed">
            ZentroApp is a leading point of sale system in Uganda, optimized for EFRIS, UGX pricing,
            and African retail workflows. We serve businesses across the continent and are expanding
            support for neighbouring markets. If you operate in Kenya,
            Tanzania, or Rwanda and need multi-currency POS,{" "}
            <a href="#contact" className="text-blue-600 font-medium hover:underline">
              contact our team
            </a>
            .
          </p>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="bg-[#0B1120] border-t border-white/10 text-gray-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-10">
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-10 mb-14">
            {/* Brand */}
            <div className="lg:col-span-2">
              <img src={LOGO_WHITE} alt="Zentro App logo" className="h-8 w-auto mb-5" />
              <p className="text-gray-500 text-sm leading-relaxed max-w-xs mb-6">
                Modern POS and inventory management built for African businesses. EFRIS certified, mobile-ready, and offline-capable.
              </p>
              <div className="flex flex-wrap gap-3 items-center">
                <MobileAppDownload variant="footer" />
                <DesktopAppDownload variant="footer" />
                <a
                  href="https://wa.me/256750440865"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gray-800 text-gray-300 text-xs font-medium hover:bg-green-700 hover:text-white transition-colors cursor-pointer"
                >
                  <FaWhatsapp />
                  WhatsApp
                </a>
              </div>
            </div>

            {/* Quick links */}
            <div>
              <h4 className="text-white text-sm font-semibold mb-5">Product</h4>
              <ul className="space-y-3">
                {[
                  { href: '#features', label: 'Features' },
                  { href: '#how-it-works', label: 'How It Works' },
                  { href: '#pricing', label: 'Pricing' },
                  { href: ANDROID_APK_DOWNLOAD_URL, label: 'Download Android App' },
                  { href: DESKTOP_WINDOWS_DOWNLOAD_URL, label: 'Download Windows App' },
                ].map((item) => (
                  <li key={item.label}>
                    <a href={item.href} className="text-sm hover:text-white transition-colors cursor-pointer">{item.label}</a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Contact */}
            <div>
              <h4 className="text-white text-sm font-semibold mb-5">Contact</h4>
              <ul className="space-y-3 text-sm">
                <li>
                  <a href="mailto:info@zentroapp.com" className="hover:text-white transition-colors">info@zentroapp.com</a>
                </li>
                <li>+256 750 440 865</li>
                <li>+256 798 997 89</li>
                <li>
                  <a href="https://wa.me/256750440865" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">
                    WhatsApp +256 750 440 865
                  </a>
                </li>
                <li className="text-gray-600">Ntinda, Kampala, Uganda</li>
              </ul>
            </div>
          </div>

          <div className="border-t border-gray-800 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-600">
            <p>&copy; {new Date().getFullYear()} ZentroApp. All rights reserved.</p>
            <div className="flex gap-6">
              <Link href="/signup" className="hover:text-gray-400 transition-colors">Start Free Trial</Link>
              <Link href="/workspace" className="hover:text-gray-400 transition-colors">Log in</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="group bg-white p-7 rounded-2xl ring-1 ring-gray-200/80 shadow-sm hover:shadow-md hover:ring-blue-200/60 transition-all duration-200 cursor-default h-full">
      <div className="w-12 h-12 bg-blue-600/10 text-blue-600 rounded-xl flex items-center justify-center mb-6 text-lg">
        {icon}
      </div>
      <h3 className="text-lg font-bold text-gray-900 mb-3">{title}</h3>
      <p className="text-gray-600 text-sm leading-relaxed">{description}</p>
    </div>
  );
}

function TestimonialCard({
  quote,
  author,
  role,
  location,
  initials,
  color = "blue",
}: {
  quote: string;
  author: string;
  role: string;
  location: string;
  initials: string;
  color?: "blue" | "violet" | "emerald";
}) {
  const avatarColor =
    color === "blue" ? "bg-blue-600" :
    color === "violet" ? "bg-violet-600" :
    "bg-emerald-600";

  return (
    <div className="bg-[#F8FAFC] rounded-2xl ring-1 ring-gray-200/80 p-7 flex flex-col h-full hover:shadow-md transition-shadow duration-200">
      <FaQuoteLeft className="text-blue-200 text-2xl mb-4" />
      <div className="flex mb-4 gap-0.5">
        {[...Array(5)].map((_, i) => (
          <FaStar key={i} className="text-yellow-400 text-sm" />
        ))}
      </div>
      <p className="text-gray-600 text-sm leading-relaxed flex-1 mb-6">"{quote}"</p>
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-full ${avatarColor} text-white flex items-center justify-center text-xs font-bold flex-shrink-0`}>
          {initials}
        </div>
        <div>
          <p className="text-gray-900 font-semibold text-sm">{author}</p>
          <p className="text-gray-400 text-xs">{role} · {location}</p>
        </div>
      </div>
    </div>
  );
}

function ContactInfoItem({
  icon,
  label,
  value,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
}) {
  return (
    <div className="flex items-start gap-4">
      <div className="w-9 h-9 rounded-lg bg-blue-600/15 border border-blue-500/20 flex items-center justify-center text-blue-400 flex-shrink-0 text-sm">
        {icon}
      </div>
      <div>
        <p className="text-gray-500 text-xs font-medium mb-0.5 uppercase tracking-wide">{label}</p>
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-gray-200 text-sm hover:text-white transition-colors">
            {value}
          </a>
        ) : (
          <p className="text-gray-200 text-sm">{value}</p>
        )}
      </div>
    </div>
  );
}

function InputField({
  label,
  type,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  type: string;
  placeholder: string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <input
        type={type}
        className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-sm"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

// ─── Animated hero device ─────────────────────────────────────────────────────

function HeroDevice() {
  const reduced = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);

  // Mouse parallax: device tilts subtly toward the cursor
  const mouseX = useRef(0);
  const mouseY = useRef(0);
  const rotateX = useRef(0);
  const rotateY = useRef(0);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (reduced) return;
    let rafId: number;

    const onMove = (e: MouseEvent) => {
      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      mouseX.current = ((e.clientX - cx) / rect.width) * 10;
      mouseY.current = ((e.clientY - cy) / rect.height) * -10;
    };

    const lerp = () => {
      rotateX.current += (mouseY.current - rotateX.current) * 0.08;
      rotateY.current += (mouseX.current - rotateY.current) * 0.08;
      setTilt({ x: rotateX.current, y: rotateY.current });
      rafId = requestAnimationFrame(lerp);
    };

    window.addEventListener("mousemove", onMove);
    rafId = requestAnimationFrame(lerp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(rafId);
    };
  }, [reduced]);

  // Floating badges that pop in around the device
  const badges = [
    { label: "UGX 5,000 sale", icon: "💳", top: "14%", left: "-28%", delay: 1.1 },
    { label: "EFRIS receipt sent", icon: "✅", top: "42%", left: "-32%", delay: 1.4 },
    { label: "Offline mode active", icon: "📶", top: "70%", left: "-24%", delay: 1.7 },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, x: 48, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      transition={{ duration: 0.8, delay: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="hidden lg:flex flex-shrink-0 w-72 xl:w-80 items-center justify-center relative"
      style={{ perspective: 1000 }}
    >
      {/* Ambient glow behind device */}
      <motion.div
        className="absolute inset-0 rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(ellipse at center, rgba(37,99,235,0.35) 0%, transparent 70%)",
          filter: "blur(24px)",
        }}
        animate={reduced ? {} : { opacity: [0.5, 0.85, 0.5], scale: [1, 1.08, 1] }}
        transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Device with float + tilt */}
      <div ref={containerRef} className="relative w-full">
        <motion.div
          animate={reduced ? {} : { y: [0, -14, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          style={{
            transform: reduced
              ? undefined
              : `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
            transformStyle: "preserve-3d",
            willChange: "transform",
          }}
        >
          <img
            src="/image/pos-device-cart.png"
            alt="ZentroApp Android POS device showing live cart and checkout"
            className="w-full drop-shadow-2xl relative z-10"
            loading="eager"
          />
        </motion.div>

        {/* Floating UI badges */}
        {badges.map(({ label, icon, top, left, delay }) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, x: -12, scale: 0.85 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
            style={{ position: "absolute", top, left }}
            className="flex items-center gap-2 bg-white/10 backdrop-blur-md border border-white/15 text-white text-xs font-medium px-3 py-1.5 rounded-full shadow-lg whitespace-nowrap z-20"
          >
            <span>{icon}</span>
            {label}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

function FaqAccordion({
  items,
}: {
  items: ReadonlyArray<{ readonly question: string; readonly answer: string }>;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const reduced = useReducedMotion();

  return (
    <dl className="space-y-3">
      {items.map((item, i) => {
        const isOpen = open === i;
        return (
          <div
            key={item.question}
            className={`rounded-2xl border transition-colors duration-200 overflow-hidden ${
              isOpen ? "border-blue-200 bg-white shadow-sm" : "border-gray-200 bg-white hover:border-blue-100"
            }`}
          >
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : i)}
              aria-expanded={isOpen}
              className="w-full flex items-center justify-between gap-4 px-6 py-5 text-left cursor-pointer"
            >
              <dt className="text-sm font-semibold text-gray-900">{item.question}</dt>
              <motion.span
                animate={{ rotate: isOpen ? 45 : 0 }}
                transition={{ duration: reduced ? 0 : 0.2 }}
                className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold"
              >
                +
              </motion.span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  key="answer"
                  initial={reduced ? {} : { height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={reduced ? {} : { height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                  style={{ overflow: "hidden" }}
                >
                  <dd className="px-6 pb-5 text-sm text-gray-600 leading-relaxed border-t border-gray-100 pt-4">
                    {item.answer}
                  </dd>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </dl>
  );
}

function BillingToggle({
  isYearly,
  onChange,
}: {
  isYearly: boolean;
  onChange: (yearly: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-center gap-4 mb-12">
      <span className={`text-sm font-medium transition-colors ${!isYearly ? "text-gray-900" : "text-gray-400"}`}>Monthly</span>
      <button
        onClick={() => onChange(!isYearly)}
        aria-pressed={isYearly}
        className="relative h-7 w-12 rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 cursor-pointer"
        style={{ backgroundColor: isYearly ? "#2563EB" : "#E2E8F0" }}
      >
        <span
          className={`absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-white shadow-sm transition-transform duration-200 ${isYearly ? "translate-x-5" : "translate-x-0"}`}
        />
      </button>
      <span className={`text-sm font-medium transition-colors ${isYearly ? "text-gray-900" : "text-gray-400"}`}>
        Yearly
        <span className="ml-2 text-xs font-semibold text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full">Save 20%</span>
      </span>
    </div>
  );
}

// Keep exported PricingCard for backward compatibility
interface PricingCardProps {
  name: string;
  price: string;
  yearlyPrice: string;
  period: string;
  features: string[];
  buttonText: string;
  highlight: boolean;
  note: string;
  theme?: "dark" | "white" | "gradient";
  isYearly: boolean;
  onSelect: () => void;
}

export function PricingCard({
  name,
  price,
  yearlyPrice,
  period,
  features,
  buttonText,
  highlight,
  isYearly,
  onSelect,
}: PricingCardProps) {
  const displayPrice = isYearly ? yearlyPrice : price;
  let icon = <FaStar className="text-blue-500" />;
  let iconBg = "bg-blue-50";
  let priceColor = "text-gray-900";
  let checkColor = "text-blue-500";
  let buttonColor = "bg-gray-900 hover:bg-gray-800";
  let cardBg = "bg-white";
  let cardBorder = "border-gray-200";
  let planNameColor = "text-gray-900";
  let buttonTextColor = "text-white";
  let arrowColor = "text-white";

  if (name.toLowerCase().includes("multi") || name.toLowerCase().includes("branch")) {
    icon = <FaBolt className="text-indigo-600" />;
    iconBg = "bg-indigo-50";
    priceColor = "text-indigo-600";
    checkColor = "text-indigo-600";
    buttonColor = "bg-indigo-600 hover:bg-indigo-700";
    cardBorder = highlight ? "border-indigo-600" : "border-indigo-200";
  } else if (name.toLowerCase().includes("premium") || name.toLowerCase().includes("efris")) {
    icon = <FaCrown className="text-yellow-400" />;
    iconBg = "bg-yellow-100";
    priceColor = "text-yellow-400";
    checkColor = "text-yellow-400";
    buttonColor = "bg-yellow-400 hover:bg-yellow-500";
    cardBg = "bg-gray-900";
    cardBorder = "border-gray-900";
    planNameColor = "text-white";
    buttonTextColor = "text-gray-900";
    arrowColor = "text-gray-900";
  }

  return (
    <div
      className={`relative ${cardBg} rounded-2xl border shadow-sm p-7 flex flex-col transition-all duration-300 ${
        highlight ? `${cardBorder} shadow-lg ring-2 ring-blue-100 z-10` : cardBorder
      }`}
    >
      {highlight && (
        <span className="absolute -top-4 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-xs font-semibold px-4 py-1 rounded-full shadow">
          Most Popular
        </span>
      )}
      <div className="flex items-center mb-4">
        <div className={`w-10 h-10 flex items-center justify-center rounded-xl ${iconBg} mr-3`}>{icon}</div>
        <h3 className={`text-xl font-bold ${planNameColor}`}>{name}</h3>
      </div>
      <div className="flex items-end mb-1">
        <span className={`text-4xl font-extrabold ${priceColor}`}>{displayPrice}</span>
      </div>
      <span className={`text-base ${planNameColor} font-medium mb-2`}>/{period}</span>
      {isYearly && price !== "0" && price !== "UGX 0" && (
        <p className="text-xs text-green-600 mb-4">Save 20% with yearly billing</p>
      )}
      <ul className="mb-6 space-y-3 text-sm flex-1">
        {features.map((feature, idx) => (
          <li key={idx} className="flex items-center text-left">
            <FaCheck className={`mr-2 text-base ${checkColor}`} />
            <span className={planNameColor}>{feature}</span>
          </li>
        ))}
      </ul>
      {name.toLowerCase().includes("efris") || name.toLowerCase().includes("premium") ? (
        <button className="w-full py-3 rounded-lg font-semibold bg-gray-400 text-white cursor-not-allowed" disabled>
          Coming Soon
        </button>
      ) : (
        <Link href="/workspace">
          <button
            className={`w-full py-3 rounded-lg font-semibold flex items-center justify-center gap-2 ${buttonColor} ${buttonTextColor} transition cursor-pointer`}
            onClick={onSelect}
          >
            {buttonText} <FaArrowRight className={`ml-1 ${arrowColor}`} />
          </button>
        </Link>
      )}
    </div>
  );
}

