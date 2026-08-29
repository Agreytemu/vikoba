import { FC } from "react";

interface ButtonProps {
  text: string | React.ReactNode;
  onClick?: (event?: React.MouseEvent<HTMLButtonElement>) => void;
  className?: string;
  disabled?: boolean;
  variant?: "primary" | "secondary";
  type?: "button" | "submit" | "reset";
}

const Button: FC<ButtonProps> = ({
  text,
  onClick,
  className,
  disabled,
  variant,
}) => {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-60";
  const styles =
    variant === "primary"
      ? "bg-blue-700 text-white shadow-soft hover:bg-blue-800 active:translate-y-px"
      : "border border-slate-300 bg-white text-ink shadow-soft hover:border-blue-400 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800";
  return (
    <button
      className={`${base} ${styles} ${className ?? ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {text}
    </button>
  );
};

export default Button;
