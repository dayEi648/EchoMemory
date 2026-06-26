import {
  type ComponentPropsWithoutRef,
  type JSX,
  memo,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ---------------------------------------------------------------------------
// 基础无样式组件 — 作为 ReactMarkdown 的 components prop 传入，避免 HTML
// 回退到浏览器默认样式。
// ---------------------------------------------------------------------------

type NativeEl<P extends keyof JSX.IntrinsicElements> =
  ComponentPropsWithoutRef<P>;

const Heading1 = ({ children, ...rest }: NativeEl<"h1">) => (
  <h1 className="ai-md-h1" {...rest}>
    {children}
  </h1>
);
const Heading2 = ({ children, ...rest }: NativeEl<"h2">) => (
  <h2 className="ai-md-h2" {...rest}>
    {children}
  </h2>
);
const Heading3 = ({ children, ...rest }: NativeEl<"h3">) => (
  <h3 className="ai-md-h3" {...rest}>
    {children}
  </h3>
);
const Paragraph = ({ children, ...rest }: NativeEl<"p">) => (
  <p className="ai-md-p" {...rest}>
    {children}
  </p>
);
const UnorderedList = ({ children, ...rest }: NativeEl<"ul">) => (
  <ul className="ai-md-ul" {...rest}>
    {children}
  </ul>
);
const OrderedList = ({ children, ...rest }: NativeEl<"ol">) => (
  <ol className="ai-md-ol" {...rest}>
    {children}
  </ol>
);
const ListItem = ({ children, ...rest }: NativeEl<"li">) => (
  <li className="ai-md-li" {...rest}>
    {children}
  </li>
);
const Blockquote = ({ children, ...rest }: NativeEl<"blockquote">) => (
  <blockquote className="ai-md-blockquote" {...rest}>
    {children}
  </blockquote>
);
const CodeBlock = ({ children, className }: NativeEl<"code">) => {
  const isInline = !className;
  if (isInline) {
    return <code className="ai-md-code-inline">{children}</code>;
  }
  // 提取语言标签用于展示（不做语法高亮以保持零依赖）
  const lang = className?.replace("language-", "") ?? undefined;
  return (
    <div className="ai-md-code-block">
      {lang && <div className="ai-md-code-lang">{lang}</div>}
      <pre className="ai-md-pre">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
};
const Link = ({ children, href, ...rest }: NativeEl<"a">) => (
  <a
    className="ai-md-link"
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    {...rest}
  >
    {children}
  </a>
);
const HorizontalRule = (props: NativeEl<"hr">) => (
  <hr className="ai-md-hr" {...props} />
);
const Strong = ({ children, ...rest }: NativeEl<"strong">) => (
  <strong className="ai-md-strong" {...rest}>
    {children}
  </strong>
);
const Emphasis = ({ children, ...rest }: NativeEl<"em">) => (
  <em className="ai-md-em" {...rest}>
    {children}
  </em>
);
const Table = ({ children, ...rest }: NativeEl<"table">) => (
  <div className="ai-md-table-wrapper">
    <table className="ai-md-table" {...rest}>
      {children}
    </table>
  </div>
);
const TableHead = ({ children, ...rest }: NativeEl<"thead">) => (
  <thead className="ai-md-thead" {...rest}>
    {children}
  </thead>
);
const TableBody = ({ children, ...rest }: NativeEl<"tbody">) => (
  <tbody className="ai-md-tbody" {...rest}>
    {children}
  </tbody>
);
const TableRow = ({ children, ...rest }: NativeEl<"tr">) => (
  <tr className="ai-md-tr" {...rest}>
    {children}
  </tr>
);
const TableHeader = ({ children, ...rest }: NativeEl<"th">) => (
  <th className="ai-md-th" {...rest}>
    {children}
  </th>
);
const TableCell = ({ children, ...rest }: NativeEl<"td">) => (
  <td className="ai-md-td" {...rest}>
    {children}
  </td>
);

const COMPONENTS = {
  h1: Heading1,
  h2: Heading2,
  h3: Heading3,
  h4: Heading3, // h4-h6 复用 h3 样式
  h5: Heading3,
  h6: Heading3,
  p: Paragraph,
  ul: UnorderedList,
  ol: OrderedList,
  li: ListItem,
  blockquote: Blockquote,
  code: CodeBlock,
  a: Link,
  hr: HorizontalRule,
  strong: Strong,
  em: Emphasis,
  table: Table,
  thead: TableHead,
  tbody: TableBody,
  tr: TableRow,
  th: TableHeader,
  td: TableCell,
};

// ---------------------------------------------------------------------------
// 公共组件
// ---------------------------------------------------------------------------

export type MarkdownContentProps = {
  /** Markdown 文本；空字符串时不渲染任何元素。 */
  content: string;
};

/**
 * 将 Markdown 文本渲染为带样式的 React 节点。
 *
 * 支持 GFM 扩展（表格、删除线、任务列表等），不使用外部语法高亮库。
 * 所有链接默认 `target="_blank"` 并携带 `rel="noopener noreferrer"`。
 */
export const MarkdownContent = memo(function MarkdownContent({
  content,
}: MarkdownContentProps) {
  if (!content) return null;

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
      {content}
    </ReactMarkdown>
  );
});
