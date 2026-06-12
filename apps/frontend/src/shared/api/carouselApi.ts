import { createBaseApi, type ApiOptions } from "./base";

export interface CarouselItem {
  id: string;
  type: "music" | "album";
  target_id: number;
  title: string;
  description: string;
  image_url: string | null;
  sort_order: number;
}

export interface CarouselCreateInput {
  type: "music" | "album";
  target_id: number;
  title: string;
  description: string;
}

export interface CarouselUpdateInput {
  title?: string;
  description?: string;
}

export const createCarouselApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 公开：列出所有轮播推图 */
    listCarousel: () => request<CarouselItem[]>("/carousel/", {}, false),

    /** 管理员：新增轮播推图 */
    createCarouselItem: (input: CarouselCreateInput) =>
      request<CarouselItem>("/carousel/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),

    /** 管理员：修改轮播推图 */
    updateCarouselItem: (itemId: string, input: CarouselUpdateInput) =>
      request<CarouselItem>(`/carousel/admin/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),

    /** 管理员：删除轮播推图 */
    deleteCarouselItem: (itemId: string) =>
      request<void>(`/carousel/admin/${itemId}`, { method: "DELETE" }),

    /** 管理员：调整推图顺序 */
    reorderCarouselItems: (ids: string[]) =>
      request<void>("/carousel/admin/reorder", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      }),
  };
};
