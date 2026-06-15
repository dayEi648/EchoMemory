import { describe, expect, it } from "vitest";

import { ApiError } from "./api/base";
import { ErrorCode } from "./constants/errorCode";
import { HttpStatus } from "./constants/httpStatus";
import { getApiErrorMessage } from "./apiError";

describe("getApiErrorMessage", () => {
  it("returns business error code description when available", () => {
    const err = new ApiError("ignored", HttpStatus.CONFLICT, ErrorCode.USER_USERNAME_EXISTS);
    expect(getApiErrorMessage(err)).toBe("用户名已被注册");
  });

  it("returns 401 status message when message is generic", () => {
    const err = new ApiError("请求失败", HttpStatus.UNAUTHORIZED);
    expect(getApiErrorMessage(err)).toBe("登录已过期，请重新登录");
  });

  it("returns 403 status message", () => {
    const err = new ApiError("请求失败", HttpStatus.FORBIDDEN);
    expect(getApiErrorMessage(err)).toBe("无权执行此操作");
  });

  it("returns 404 status message", () => {
    const err = new ApiError("请求失败", HttpStatus.NOT_FOUND);
    expect(getApiErrorMessage(err)).toBe("资源不存在");
  });

  it("returns 409 status message", () => {
    const err = new ApiError("请求失败", HttpStatus.CONFLICT);
    expect(getApiErrorMessage(err)).toBe("请求冲突，请稍后重试");
  });

  it("returns 422 status message", () => {
    const err = new ApiError("请求失败", HttpStatus.UNPROCESSABLE_ENTITY);
    expect(getApiErrorMessage(err)).toBe("请求参数有误");
  });

  it("returns 429 status message", () => {
    const err = new ApiError("请求失败", HttpStatus.TOO_MANY_REQUESTS);
    expect(getApiErrorMessage(err)).toBe("操作过于频繁，请稍后再试");
  });

  it("returns backend message for unknown business code without status hint", () => {
    const err = new ApiError("自定义后端提示", HttpStatus.BAD_REQUEST, 19999);
    expect(getApiErrorMessage(err)).toBe("自定义后端提示");
  });

  it("uses fallback for unknown ApiError without useful message", () => {
    const err = new ApiError("请求失败", HttpStatus.BAD_REQUEST);
    expect(getApiErrorMessage(err, "操作失败")).toBe("操作失败");
  });

  it("handles non-ApiError Error", () => {
    expect(getApiErrorMessage(new Error("网络断开"))).toBe("网络断开");
  });

  it("uses fallback for unknown values", () => {
    expect(getApiErrorMessage(null, "保存失败")).toBe("保存失败");
  });
});
