type Props = {
  children: React.ReactNode;
  type?: "button" | "submit";
  onClick?: () => void;
  disabled?: boolean;
};

export function PrimaryButton({ children, type = "button", onClick, disabled }: Props) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="font-label w-full rounded-full bg-primary py-4 uppercase tracking-[0.2em] text-on-primary transition-all duration-300 hover:bg-on-primary-fixed-variant active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}
