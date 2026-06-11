import type { ReactNode } from "react";

interface PaginatedPageLayoutProps {
  /** 页头区域：标题、筛选、Tab 等固定在上方的内容。 */
  header?: ReactNode;
  /** 主内容区域。 */
  children: ReactNode;
  /** 底部分页栏；内容较少时会自动贴齐可视区域底部。 */
  footer?: ReactNode;
  className?: string;
}

/** 分页列表页布局：短内容时将 footer 推至页面底部，长内容时随列表自然下移。 */
export const PaginatedPageLayout = ({
  header,
  children,
  footer,
  className,
}: PaginatedPageLayoutProps) => (
  <div className={["paginated-page", className].filter(Boolean).join(" ")}>
    {header ? <div className="paginated-page__header">{header}</div> : null}
    <div className="paginated-page__body">{children}</div>
    {footer ? <div className="paginated-page__footer">{footer}</div> : null}
  </div>
);
