export function AuthCard({ children }: { children: React.ReactNode }) {
  return (
    <main className="soft-glow-background relative flex min-h-screen w-full items-center justify-center px-margin-mobile pt-14 pb-6">
      <div className="relative z-10 flex w-full max-w-[440px] flex-col gap-3">
        <div className="card-elevation rounded-[24px] bg-surface-container-lowest px-6 py-6 md:px-8 md:py-7">
          {children}
        </div>
        <div className="flex justify-center gap-6 opacity-40">
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
