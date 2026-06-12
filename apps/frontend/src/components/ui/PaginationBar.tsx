/** 分页栏组件。
 *
 * 显示前一页 / 当前页 / 下一页按钮，并支持手动输入页码跳转。
 * 适用于所有需要分页查询的页面。
 */
import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { motion } from "framer-motion";

interface PaginationBarProps {
  /** 当前页码（从 0 开始）。 */
  page: number;
  /** 总页数。 */
  totalPages: number;
  /** 页码变化回调，传入新的 0-based 页码。 */
  onPageChange: (page: number) => void;
  /** 是否正在加载中（禁用按钮）。 */
  loading?: boolean;
  /** 总条数，用于显示信息。 */
  total?: number;
  /** 当前每页条数。 */
  pageSize?: number;
  /** 每页条数变化回调。 */
  onPageSizeChange?: (size: number) => void;
  /** 可选的每页条数选项，默认 [10, 20, 50]。 */
  pageSizeOptions?: number[];
}

export const PaginationBar = ({
  page,
  totalPages,
  onPageChange,
  loading = false,
  total,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
}: PaginationBarProps) => {
  const [inputValue, setInputValue] = useState("");

  const handleJump = () => {
    const target = Number(inputValue);
    if (Number.isNaN(target)) return;
    const zeroBased = target - 1;
    if (zeroBased >= 0 && zeroBased < totalPages) {
      onPageChange(zeroBased);
      setInputValue("");
    }
  };

  const prevPage = page - 1;
  const nextPage = page + 1;

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="pagination-bar">
      {onPageSizeChange && pageSize !== undefined && (
        <div className="pagination-left">
          <span className="pagination-label">每页</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="pagination-size-select"
            disabled={loading}
          >
            {pageSizeOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span className="pagination-label">条</span>
        </div>
      )}

      <div className="pagination-center">
        <motion.button
          className="pagination-btn"
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0 || loading}
          whileTap={{ scale: 0.95 }}
          type="button"
          title="上一页"
        >
          <ChevronLeft size={16} />
        </motion.button>

        {prevPage >= 0 && (
          <motion.button
            className="pagination-btn"
            onClick={() => onPageChange(prevPage)}
            disabled={loading}
            whileTap={{ scale: 0.95 }}
            type="button"
          >
            {prevPage + 1}
          </motion.button>
        )}

        <motion.button
          className="pagination-btn active"
          disabled
          type="button"
        >
          {page + 1}
        </motion.button>

        {nextPage < totalPages && (
          <motion.button
            className="pagination-btn"
            onClick={() => onPageChange(nextPage)}
            disabled={loading}
            whileTap={{ scale: 0.95 }}
            type="button"
          >
            {nextPage + 1}
          </motion.button>
        )}

        <motion.button
          className="pagination-btn"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1 || loading}
          whileTap={{ scale: 0.95 }}
          type="button"
          title="下一页"
        >
          <ChevronRight size={16} />
        </motion.button>
      </div>

      <div className="pagination-right" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span className="pagination-info">
          第
          <input
            type="number"
            min={1}
            max={totalPages}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleJump();
            }}
            onBlur={handleJump}
            disabled={loading || totalPages <= 1}
            style={{
              width: 44,
              textAlign: "center",
              margin: "0 4px",
              fontSize: 13,
              padding: "2px 4px",
            }}
          />
          / {totalPages} 页
        </span>
        {total !== undefined && (
          <span className="pagination-info" style={{ color: "var(--color-muted)" }}>
            共 {total} 条
          </span>
        )}
      </div>
    </div>
  );
};
