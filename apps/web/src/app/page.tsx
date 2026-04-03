import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-4">JobXplore</h1>
      <p className="text-muted-foreground mb-8 text-center max-w-lg">
        AI-powered job search automation. Scrape, analyze, score alignment, and
        optimize your resume — all in one place.
      </p>
      <div className="flex gap-4">
        <Link
          href="/login"
          className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition"
        >
          Log in
        </Link>
        <Link
          href="/signup"
          className="px-6 py-3 border border-border rounded-lg hover:bg-accent transition"
        >
          Sign up
        </Link>
      </div>
    </main>
  );
}
