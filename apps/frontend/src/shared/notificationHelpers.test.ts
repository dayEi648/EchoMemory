import { describe, expect, it } from "vitest";
import {
  formatBadge,
  NOTIFICATION_ICON_MAP,
  NOTIFICATION_LABEL_MAP,
} from "./notificationHelpers";

describe("notificationHelpers", () => {
  describe("formatBadge", () => {
    it("returns the number as string for small counts", () => {
      expect(formatBadge(0)).toBe("0");
      expect(formatBadge(5)).toBe("5");
      expect(formatBadge(9)).toBe("9");
    });

    it('returns "9+" for 10 or more', () => {
      expect(formatBadge(10)).toBe("9+");
      expect(formatBadge(99)).toBe("9+");
    });
  });

  describe("NOTIFICATION_ICON_MAP", () => {
    it("has entries for all 5 notification types", () => {
      for (let t = 0; t <= 4; t++) {
        expect(NOTIFICATION_ICON_MAP[t]).toBeDefined();
      }
    });
  });

  describe("NOTIFICATION_LABEL_MAP", () => {
    it("has Chinese labels for all 5 notification types", () => {
      expect(NOTIFICATION_LABEL_MAP[0]).toBe("关注了你");
      expect(NOTIFICATION_LABEL_MAP[1]).toBe("回复了你的评论");
      expect(NOTIFICATION_LABEL_MAP[2]).toBe("赞了你的评论");
      expect(NOTIFICATION_LABEL_MAP[3]).toBe("赞了你的动态");
      expect(NOTIFICATION_LABEL_MAP[4]).toBe("评论了你的动态");
    });
  });
});
