import { FC, ReactNode } from "react";
import { useInView } from "@/hooks/useInView";

interface RevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  ariaLabel?: string;
}

// Fades + lifts its children into place the first time they enter the viewport.
const Reveal: FC<RevealProps> = ({
  children,
  className = "",
  delay = 0,
  ariaLabel,
}) => {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <div
      ref={ref}
      aria-label={ariaLabel}
      className={`reveal ${inView ? "is-visible" : ""} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
};

export default Reveal;
