export function AuthCard({ children }: { children: React.ReactNode }) {
  return (
    <main className="soft-glow-background relative flex min-h-screen w-full items-center justify-center overflow-hidden pt-24 pb-12">
      <div className="relative z-10 w-full max-w-[480px] px-margin-mobile md:px-0">
        <div className="card-elevation rounded-[24px] bg-surface-container-lowest p-8 md:p-16">
          {children}
        </div>
        <div className="mt-12 flex justify-center gap-6 opacity-40">
          <a href="#" className="font-label hover:opacity-100">
            Privacy
          </a>
          <a href="#" className="font-label hover:opacity-100">
            Terms
          </a>
          <a href="#" className="font-label hover:opacity-100">
            Legal
          </a>
        </div>
      </div>
    </main>
  );
}
