import type { LucideIcon } from "lucide-react";

interface PageTitleProps {
  icon?: LucideIcon;
  iconSize?: number;
  children: React.ReactNode;
}

export const PageTitle = ({ icon: Icon, iconSize = 20, children }: PageTitleProps) => (
  <h1 className="page-title">
    {Icon && (
      <Icon
        size={iconSize}
        style={{ display: "inline", verticalAlign: "-2px", marginRight: 8 }}
      />
    )}
    {children}
  </h1>
);
