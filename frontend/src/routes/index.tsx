import { createFileRoute, Link } from "@tanstack/react-router";
import { JoiMascot } from "@/components/joi/JoiMascot";
import { SparkleField } from "@/components/joi/SparkleField";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "JOI — your AI companion" },
      { name: "description", content: "Meet JOI, a living digital companion that remembers, learns, and grows with you." },
      { property: "og:title", content: "JOI — your AI companion" },
      { property: "og:description", content: "A living digital companion that remembers, learns, and grows with you." },
    ],
  }),
  component: LandingPage,
});

const FEATURES = [
  { icon: "🧠", title: "Memory System", text: "JOI remembers previous conversations and important information." },
  { icon: "🎭", title: "Adaptive Personality", text: "Emotion-aware interactions and dynamic expressions." },
  { icon: "🎤", title: "Voice First", text: "Talk naturally with seamless voice conversations." },
  { icon: "⚡", title: "Semantic Memory", text: "Intelligent context recall and long-term memory." },
  { icon: "✨", title: "Living Character", text: "Animated reactions, emotions, sleeping, waking, and expressions." },
  { icon: "🔒", title: "Private & Local Friendly", text: "Designed to support local and cloud AI models." },
];

function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      {/* Hero */}
      <section className="relative flex min-h-screen flex-col items-center justify-center px-6 pt-10 text-center">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 50% 45%, rgba(255,199,42,0.18), transparent 70%), radial-gradient(ellipse 40% 30% at 50% 55%, rgba(248,157,37,0.12), transparent 70%)",
          }}
        />
        <SparkleField density={46} />

        {/* Top bar */}
        <header className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between px-6 py-5 sm:px-10">
          <div className="font-pixel text-2xl tracking-wider text-primary">
            JOI <span className="text-secondary">✦</span>
          </div>
          <Link
            to="/chat"
            className="rounded-full border border-border bg-surface/70 px-4 py-1.5 text-xs uppercase tracking-widest text-muted-foreground transition hover:text-foreground"
          >
            Enter
          </Link>
        </header>

        <div className="relative z-[1] flex flex-col items-center">
          <div className="animate-joi-float">
            <div className="animate-joi-breathe">
              <JoiMascot expression="happy" size={340} className="sm:!h-[420px] sm:!w-[420px]" />
            </div>
          </div>

          <h1 className="font-pixel mt-8 text-5xl sm:text-7xl text-primary drop-shadow-[0_0_20px_rgba(255,199,42,0.35)]">
            Meet JOI
          </h1>
          <p className="mt-4 max-w-xl text-base sm:text-lg text-muted-foreground">
            Your AI companion that remembers, learns, and grows with you.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/chat"
              className="glow-primary rounded-full bg-primary px-7 py-3 font-pixel text-base font-semibold text-primary-foreground transition hover:-translate-y-0.5"
            >
              Start Chatting
            </Link>
            <a
              href="#features"
              className="rounded-full border border-border bg-surface/60 px-7 py-3 font-pixel text-base text-foreground transition hover:border-primary/40 hover:text-primary"
            >
              Learn More
            </a>
          </div>
        </div>

        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-xs text-muted-foreground/70">
          scroll to explore ↓
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative px-6 py-24 sm:px-10">
        <SparkleField density={20} />
        <div className="relative z-[1] mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <p className="font-pixel text-xs uppercase tracking-[0.4em] text-secondary">capabilities</p>
            <h2 className="mt-3 font-pixel text-3xl sm:text-5xl text-foreground">
              A companion, not a chatbot
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
              Built around character, memory, and presence — JOI feels alive on screen.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <div
                key={f.title}
                className="glass-card group relative overflow-hidden rounded-2xl p-6 transition hover:-translate-y-1 hover:border-primary/30"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div
                  className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-0 blur-3xl transition group-hover:opacity-60"
                  style={{ background: "radial-gradient(circle, #FFC72A, transparent 70%)" }}
                />
                <div className="font-pixel text-3xl">{f.icon}</div>
                <h3 className="font-pixel mt-3 text-xl text-primary">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA strip */}
      <section className="relative px-6 pb-24">
        <div className="glass-card mx-auto flex max-w-4xl flex-col items-center gap-5 rounded-3xl p-10 text-center sm:p-14">
          <JoiMascot expression="excited" size={120} />
          <h3 className="font-pixel text-2xl sm:text-3xl text-foreground">Ready when you are.</h3>
          <p className="max-w-md text-muted-foreground">
            Say hi to JOI. The longer you talk, the better the memory becomes.
          </p>
          <Link
            to="/chat"
            className="glow-primary rounded-full bg-primary px-8 py-3 font-pixel font-semibold text-primary-foreground"
          >
            Start Chatting
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/60 px-6 py-10 text-center">
        <div className="font-pixel text-lg text-primary">JOI-lite</div>
        <p className="mt-1 text-sm text-muted-foreground">Built with ❤️ and curiosity.</p>
      </footer>
    </div>
  );
}
