import { ApiError } from "./api/base";
import { ErrorCode, getErrorCodeDescription } from "./constants/errorCode";
import { HttpStatus } from "./constants/httpStatus";

const GENERIC_MESSAGES = new Set(["请求失败", "Request failed", ""]);

/** 按 HTTP 状态码返回中文兜底提示。 */
function getStatusMessage(status: number): string | undefined {
  switch (status) {
    case HttpStatus.UNAUTHORIZED:
      return "登录已过期，请重新登录";
    case HttpStatus.FORBIDDEN:
      return "无权执行此操作";
    case HttpStatus.NOT_FOUND:
      return "资源不存在";
    case HttpStatus.CONFLICT:
      return "请求冲突，请稍后重试";
    case HttpStatus.UNPROCESSABLE_ENTITY:
      return "请求参数有误";
    case HttpStatus.TOO_MANY_REQUESTS:
      return "操作过于频繁，请稍后再试";
    default:
      return undefined;
  }
}

/** 将 API 异常转为面向用户的中文提示。 */
export function getApiErrorMessage(err: unknown, fallback = "请求失败"): string {
  if (!(err instanceof ApiError)) {
    return err instanceof Error && err.message ? err.message : fallback;
  }

  if (err.code !== undefined && err.code !== ErrorCode.SUCCESS) {
    const byCode = getErrorCodeDescription(err.code);
    if (byCode !== "请求失败") {
      return byCode;
    }
  }

  const statusMsg = getStatusMessage(err.status);
  if (statusMsg) {
    return statusMsg;
  }

  if (err.message && !GENERIC_MESSAGES.has(err.message)) {
    return err.message;
  }

  return fallback;
}
