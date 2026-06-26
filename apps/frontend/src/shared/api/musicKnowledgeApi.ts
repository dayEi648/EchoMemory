import type {
  MusicKnowledgeIngestResult,
  MusicKnowledgeSourceList,
  MusicKnowledgeDeleteResult,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createMusicKnowledgeApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 上传文档到音乐知识库（同名文档会覆盖旧数据）。 */
    uploadDocument: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<MusicKnowledgeIngestResult>(
        "/admin/music-knowledge/documents",
        {
          method: "POST",
          body: formData,
          // 不设置 Content-Type，让浏览器自动生成含 boundary 的 multipart/form-data
        },
      );
    },

    /** 列出已入库的音乐知识库文档 source 列表。 */
    listDocuments: (params?: { limit?: number; offset?: number }) => {
      const limit = params?.limit ?? 20;
      const offset = params?.offset ?? 0;
      return request<MusicKnowledgeSourceList>(
        `/admin/music-knowledge/documents?limit=${limit}&offset=${offset}`,
      );
    },

    /** 删除指定 source 的文档及其全部向量片段。 */
    deleteDocument: (source: string) =>
      request<MusicKnowledgeDeleteResult>(
        `/admin/music-knowledge/documents/${encodeURIComponent(source)}`,
        { method: "DELETE" },
      ),
  };
};
