import type { LucideIcon } from "lucide-react";

type AccentVariant = "pink" | "teal" | "lavender" | "peach" | "ochre" | "mint" | "coral";

interface PageTitleProps {
  icon?: LucideIcon;
  iconSize?: number;
  iconAccent?: AccentVariant;
  children: React.ReactNode;
}

export const PageTitle = ({
  icon: Icon,
  iconSize = 20,
  iconAccent = "coral",
  children,
}: PageTitleProps) => (
  <h1 className="page-title">
    {Icon && (
      <span
        className={`icon-accent-bg icon-accent-bg--${iconAccent}`}
        style={{
          display: "inline-flex",
          width: 32,
          height: 32,
          verticalAlign: "-6px",
          marginRight: 10,
        }}
      >
        <Icon size={iconSize} />
      </span>
    )}
    {children}
  </h1>
);
