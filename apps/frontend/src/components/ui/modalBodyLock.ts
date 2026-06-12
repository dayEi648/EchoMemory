/** 嵌套 Modal 时按引用计数锁定 body 滚动，仅最外层关闭后恢复。 */

let lockCount = 0;

export function lockModalBodyScroll(): void {
  lockCount += 1;
  if (lockCount === 1) {
    document.body.style.overflow = "hidden";
  }
}

export function unlockModalBodyScroll(): void {
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0) {
    document.body.style.overflow = "";
  }
}
