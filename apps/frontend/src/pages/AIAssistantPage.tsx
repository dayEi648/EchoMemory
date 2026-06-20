import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  MessageSquarePlus,
  PanelLeftOpen,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { aiConversationApi } from "../shared/api/instances";
import { getApiErrorMessage } from "../shared/apiError";
import type {
  AIConversation,
  AIConversationMessage,
  AIConversationRole,
  AIStreamChunk,
} from "../shared/api/types";
import { useAuthStore } from "../shared/stores/authStore";
import { formatRelativeTime } from "../shared/utils";
import { EmptyState } from "../components/ui/EmptyState";
import { ConfirmDeleteModal } from "../components/ui/ConfirmDeleteModal";

type UIChatMessage = AIConversationMessage & {
  id: string;
  streaming?: boolean;
  createdAt: string;
  /** 失败时记录对应用户消息，用于重试 */
  retryContent?: string;
  /** 该消息的思考是否已结束 */
  reasoningComplete?: boolean;
};

const generateId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
const nowIso = () => new Date().toISOString();
const MESSAGE_TYPE_ORDER: AIConversationRole[] = ["system", "human", "ai", "tool"];
const MESSAGE_TYPE_LABELS: Record<AIConversationRole, string> = {
  system: "系统",
  human: "用户",
  ai: "AI",
  tool: "工具",
};
const DEFAULT_MESSAGE_TYPES: AIConversationRole[] = ["human", "ai"];

const formatContentBlocks = (blocks: unknown[]): string =>
  blocks
    .map((block) => {
      if (
        typeof block === "object" &&
        block !== null &&
        "text" in block &&
        typeof block.text === "string"
      ) {
        return block.text;
      }
      return JSON.stringify(block, null, 2);
    })
    .join("\n\n");

const formatMessageContent = (message: AIConversationMessage): string => {
  if (typeof message.content === "string" && message.content) {
    if (message.role === "tool" && message.content.startsWith("[")) {
      try {
        const parsed = JSON.parse(message.content);
        if (Array.isArray(parsed)) {
          return formatContentBlocks(parsed);
        }
      } catch {
        // 历史工具消息不一定是 JSON，按原始文本展示。
      }
    }
    return message.content;
  }
  if (Array.isArray(message.content)) {
    return formatContentBlocks(message.content);
  }
  if (message.tool_calls?.length) {
    return JSON.stringify(message.tool_calls, null, 2);
  }
  return "";
};

export const AIAssistantPage = () => {
  const navigate = useNavigate();
  const currentUser = useAuthStore((state) => state.user);
  const isAdmin = currentUser?.role === 2 || currentUser?.role === 3;

  const [conversations, setConversations] = useState<AIConversation[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [isDraft, setIsDraft] = useState(false);
  const [messages, setMessages] = useState<UIChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<AIConversation | null>(null);
  const [reasoningMap, setReasoningMap] = useState<Record<string, string>>({});
  const [showReasoning, setShowReasoning] = useState<Record<string, boolean>>({});
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState("");
  const [selectedMessageTypes, setSelectedMessageTypes] =
    useState<AIConversationRole[]>(DEFAULT_MESSAGE_TYPES);
  const [messageFilterExpanded, setMessageFilterExpanded] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const skipMessageLoadForIdRef = useRef<number | null>(null);
  const currentIdRef = useRef<number | null>(null);

  useEffect(() => {
    currentIdRef.current = currentId;
  }, [currentId]);

  const currentConversation = useMemo(
    () => conversations.find((c) => c.id === currentId) ?? null,
    [conversations, currentId],
  );

  const hasActiveChat = currentConversation != null || isDraft;

  useEffect(() => {
    if (!isAdmin) {
      setSelectedMessageTypes(DEFAULT_MESSAGE_TYPES);
      setMessageFilterExpanded(true);
    }
  }, [isAdmin]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadingList(true);
    aiConversationApi
      .listConversations({ limit: 100 })
      .then((res) => {
        if (cancelled) return;
        setConversations((prev) => {
          const items = res.items ?? [];
          const activeId = currentIdRef.current;
          if (activeId == null) return items;
          const hasCurrent = items.some((c) => c.id === activeId);
          if (hasCurrent) return items;
          const current = prev.find((c) => c.id === activeId);
          return current ? [current, ...items] : items;
        });
      })
      .catch((err) => {
        toast.error(getApiErrorMessage(err, "加载会话列表失败"));
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (currentId == null) {
      setMessages([]);
      return;
    }
    if (skipMessageLoadForIdRef.current === currentId) {
      skipMessageLoadForIdRef.current = null;
      setLoadingMessages(false);
      return;
    }

    let cancelled = false;
    setLoadingMessages(true);
    aiConversationApi
      .getMessages(currentId, { messageTypes: selectedMessageTypes })
      .then((res) => {
        if (cancelled) return;
        const restoredReasoning: Record<string, string> = {};
        const uiMessages: UIChatMessage[] = (res.messages ?? []).map((m) => {
          const id = generateId();
          if (m.reasoning_content) {
            restoredReasoning[id] = m.reasoning_content;
          }
          return {
            ...m,
            id,
            createdAt: m.created_at ?? nowIso(),
            reasoningComplete: true,
          };
        });
        setMessages(uiMessages);
        setReasoningMap(restoredReasoning);
        setShowReasoning({});
      })
      .catch((err) => {
        toast.error(getApiErrorMessage(err, "加载消息失败"));
      })
      .finally(() => {
        if (!cancelled) setLoadingMessages(false);
      });

    return () => {
      cancelled = true;
    };
  }, [currentId, selectedMessageTypes]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // 输入框自动增高
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const handleNewConversation = () => {
    if (isStreaming) return;
    currentIdRef.current = null;
    setCurrentId(null);
    setIsDraft(true);
    setMessages([]);
    setReasoningMap({});
    setShowReasoning({});
    setInput("");
    inputRef.current?.focus();
  };

  const handleSelectConversation = (id: number) => {
    if (isStreaming) return;
    currentIdRef.current = id;
    setCurrentId(id);
    setIsDraft(false);
  };

  const processStreamChunk = (
    chunk: AIStreamChunk,
    aiMessageId: string,
    reasoningRef: { current: string },
  ) => {
    if (chunk.type === "content") {
      // 首条消息的第一个 content chunk 可能携带会话元数据
      if (chunk.meta?.conversation) {
        const conv = chunk.meta.conversation as AIConversation;
        setConversations((prev) => {
          if (prev.some((c) => c.id === conv.id)) return prev;
          return [conv, ...prev];
        });
        skipMessageLoadForIdRef.current = conv.id;
        currentIdRef.current = conv.id;
        setCurrentId(conv.id);
        setIsDraft(false);
      }
      if (chunk.data) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMessageId
              ? { ...m, content: (m.content as string) + chunk.data }
              : m,
          ),
        );
      }
    } else if (chunk.type === "reasoning") {
      reasoningRef.current += chunk.data;
      setReasoningMap((prev) => ({ ...prev, [aiMessageId]: reasoningRef.current }));
    } else if (chunk.type === "error") {
      throw new Error(chunk.data || "AI 响应失败");
    }
  };

  const finalizeAIResponse = (aiMessageId: string) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== aiMessageId) return m;
        const text = (m.content as string) ?? "";
        return {
          ...m,
          content: text.trim() === "" ? "（AI 没有回复内容）" : text,
          streaming: false,
          reasoningComplete: true,
        };
      }),
    );
  };

  const refreshConversationList = () => {
    aiConversationApi
      .listConversations({ limit: 100 })
      .then((res) => {
        setConversations((prev) => {
          const items = res.items ?? [];
          const activeId = currentIdRef.current;
          if (activeId == null) return items;
          const hasCurrent = items.some((c) => c.id === activeId);
          if (hasCurrent) return items;
          const current = prev.find((c) => c.id === activeId);
          return current ? [current, ...items] : items;
        });
      })
      .catch(() => {
        // 忽略刷新失败
      });
  };

  const sendToExistingConversation = async (
    content: string,
    appendUserMessage = true,
  ) => {
    if (currentId == null) return;

    if (appendUserMessage) {
      const userMessage: UIChatMessage = {
        id: generateId(),
        role: "human",
        content,
        createdAt: nowIso(),
      };
      setMessages((prev) => [...prev, userMessage]);
    }
    setIsStreaming(true);

    const aiMessageId = generateId();
    const aiMessage: UIChatMessage = {
      id: aiMessageId,
      role: "ai",
      content: "",
      createdAt: nowIso(),
      streaming: true,
    };
    setMessages((prev) => [...prev, aiMessage]);

    const reasoningRef = { current: "" };
    try {
      const stream = aiConversationApi.streamMessage(currentId, content);
      for await (const chunk of stream) {
        if (chunk.type === "done") break;
        processStreamChunk(chunk, aiMessageId, reasoningRef);
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, "AI 响应失败"));
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMessageId
            ? {
                ...m,
                content: "（响应失败）",
                streaming: false,
                retryContent: content,
                reasoningComplete: true,
              }
            : m,
        ),
      );
    } finally {
      setIsStreaming(false);
      finalizeAIResponse(aiMessageId);
      refreshConversationList();
    }
  };

  const sendFirstMessage = async (content: string) => {
    const userMessage: UIChatMessage = {
      id: generateId(),
      role: "human",
      content,
      createdAt: nowIso(),
    };
    const aiMessageId = generateId();
    const aiMessage: UIChatMessage = {
      id: aiMessageId,
      role: "ai",
      content: "",
      createdAt: nowIso(),
      streaming: true,
    };
    setMessages([userMessage, aiMessage]);
    setIsStreaming(true);

    const reasoningRef = { current: "" };
    try {
      const stream = aiConversationApi.streamFirstMessage(content);
      for await (const chunk of stream) {
        if (chunk.type === "done") break;
        processStreamChunk(chunk, aiMessageId, reasoningRef);
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, "创建会话失败"));
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMessageId
            ? {
                ...m,
                content: "（创建会话失败）",
                streaming: false,
                retryContent: content,
                reasoningComplete: true,
              }
            : m,
        ),
      );
    } finally {
      setIsStreaming(false);
      finalizeAIResponse(aiMessageId);
      refreshConversationList();
    }
  };

  const handleSend = async () => {
    const content = input.trim();
    if (!content || isStreaming) return;

    setInput("");
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }

    if (isDraft) {
      await sendFirstMessage(content);
      return;
    }

    await sendToExistingConversation(content);
  };

  const handleRetry = async (aiMessageId: string) => {
    const failedMessage = messages.find((m) => m.id === aiMessageId);
    if (!failedMessage?.retryContent || isStreaming) return;

    // 移除失败的 AI 消息，重新发送对应用户消息
    setMessages((prev) => prev.filter((m) => m.id !== aiMessageId));

    if (isDraft || currentId == null) {
      await sendFirstMessage(failedMessage.retryContent);
    } else {
      await sendToExistingConversation(failedMessage.retryContent, false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await aiConversationApi.deleteConversation(deleteTarget.id);
      setConversations((prev) => prev.filter((c) => c.id !== deleteTarget.id));
      if (currentId === deleteTarget.id) {
        currentIdRef.current = null;
        setCurrentId(null);
        setIsDraft(false);
        setMessages([]);
      }
      toast.success("会话已删除");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "删除会话失败"));
    } finally {
      setDeleteTarget(null);
    }
  };

  const toggleReasoning = (id: string) => {
    setShowReasoning((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleTitleClick = () => {
    if (isStreaming || !currentConversation) return;
    setEditTitleValue(currentConversation.title);
    setIsEditingTitle(true);
    setTimeout(() => titleInputRef.current?.focus(), 0);
  };

  const handleTitleSave = async () => {
    if (!currentConversation || isStreaming) return;
    const trimmed = editTitleValue.trim();
    if (!trimmed || trimmed === currentConversation.title) {
      setIsEditingTitle(false);
      return;
    }
    try {
      const updated = await aiConversationApi.updateTitle(
        currentConversation.id,
        trimmed,
      );
      setConversations((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c)),
      );
      setIsEditingTitle(false);
      toast.success("标题已更新");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "更新标题失败"));
    }
  };

  const handleTitleCancel = () => {
    setIsEditingTitle(false);
    setEditTitleValue(currentConversation?.title ?? "");
  };

  const handleTitleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void handleTitleSave();
    } else if (e.key === "Escape") {
      handleTitleCancel();
    }
  };

  const toggleMessageType = (messageType: AIConversationRole) => {
    setSelectedMessageTypes((current) => {
      const next = current.includes(messageType)
        ? current.filter((item) => item !== messageType)
        : [...current, messageType];
      if (next.length === 0) {
        return current;
      }
      return MESSAGE_TYPE_ORDER.filter((item) => next.includes(item));
    });
  };

  const renderChatHeader = () => {
    if (isDraft) {
      return (
        <div className="ai-assistant-chat-header">
          <span className="ai-chat-title">新对话</span>
        </div>
      );
    }
    if (currentConversation) {
      return (
        <div className="ai-assistant-chat-header">
          {isEditingTitle ? (
            <input
              ref={titleInputRef}
              className="ai-chat-title-input"
              type="text"
              value={editTitleValue}
              onChange={(e) => setEditTitleValue(e.target.value)}
              onBlur={() => void handleTitleSave()}
              onKeyDown={handleTitleKeyDown}
              disabled={isStreaming}
              maxLength={200}
            />
          ) : (
            <span
              className="ai-chat-title ai-chat-title--editable"
              onClick={handleTitleClick}
              title="点击修改标题"
            >
              {currentConversation.title}
            </span>
          )}
          <span className="ai-chat-model">{currentConversation.model}</span>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="ai-assistant-page">
      {/* 顶栏 */}
      <header className="ai-assistant-topbar">
        <button
          type="button"
          className="ai-assistant-back"
          onClick={() => navigate(-1)}
          title="返回"
        >
          <ChevronLeft size={18} />
          <span>返回</span>
        </button>
        <div className="ai-assistant-title">
          <Bot size={20} />
          <span>AI 助手</span>
        </div>
        <div className="ai-assistant-topbar-spacer" />
      </header>

      {/* 主体 */}
      <div className="ai-assistant-body">
        {/* 左侧会话列表 */}
        {sidebarVisible && (
          <aside className="ai-assistant-sidebar">
            <div className="ai-assistant-sidebar-header">
              <span className="ai-sidebar-label">会话</span>
              <button
                type="button"
                className="ai-assistant-icon-btn"
                onClick={() => setSidebarVisible(false)}
                title="收起"
              >
                <PanelLeftOpen size={18} />
              </button>
            </div>

            <button
              type="button"
              className="ai-assistant-new-btn"
              onClick={handleNewConversation}
              disabled={isStreaming}
            >
              <MessageSquarePlus size={16} />
              <span>新建对话</span>
            </button>

            <div className="ai-assistant-conversation-list">
              {loadingList ? (
                <div className="ai-assistant-empty">加载中...</div>
              ) : conversations.length === 0 ? (
                <div className="ai-assistant-empty">暂无会话</div>
              ) : (
                conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`ai-assistant-conversation-item ${currentId === conv.id ? "active" : ""}`}
                    onClick={() => handleSelectConversation(conv.id)}
                    title={conv.title}
                  >
                    <Sparkles size={14} />
                    <div className="ai-conversation-meta">
                      <span className="ai-conversation-title">{conv.title}</span>
                      <span className="ai-conversation-time">
                        {formatRelativeTime(conv.updated_at)}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="ai-assistant-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(conv);
                      }}
                      title="删除会话"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>
        )}

        {/* 右侧聊天区 */}
        <main className="ai-assistant-chat">
          {!sidebarVisible && (
            <button
              type="button"
              className="ai-assistant-sidebar-expand"
              onClick={() => setSidebarVisible(true)}
              title="展开会话列表"
            >
              <PanelLeftOpen size={18} />
            </button>
          )}

          {!hasActiveChat ? (
            <div className="ai-assistant-welcome">
              <EmptyState
                icon={Bot}
                title="AI 助手"
                description="选择一个会话开始对话，或点击左侧新建对话。"
              />
            </div>
          ) : (
            <>
              {renderChatHeader()}

              {isAdmin && currentConversation && (
                <section className="ai-message-filter">
                  <button
                    type="button"
                    className="ai-message-filter__toggle"
                    aria-expanded={messageFilterExpanded}
                    aria-controls="ai-message-filter-options"
                    aria-label={
                      messageFilterExpanded
                        ? "收起消息视图筛选"
                        : "展开消息视图筛选"
                    }
                    onClick={() =>
                      setMessageFilterExpanded((expanded) => !expanded)
                    }
                  >
                    <span className="ai-message-filter__heading">
                      <SlidersHorizontal size={15} />
                      <span>消息视图</span>
                    </span>
                    <span className="ai-message-filter__summary">
                      {selectedMessageTypes
                        .map((messageType) => MESSAGE_TYPE_LABELS[messageType])
                        .join("、")}
                    </span>
                    <ChevronRight
                      size={15}
                      className={`ai-message-filter__chevron ${
                        messageFilterExpanded
                          ? "ai-message-filter__chevron--expanded"
                          : ""
                      }`}
                    />
                  </button>

                  {messageFilterExpanded && (
                    <fieldset
                      id="ai-message-filter-options"
                      className="ai-message-filter__options"
                      aria-label="消息类型筛选"
                    >
                      <legend className="sr-only">消息类型筛选</legend>
                      {MESSAGE_TYPE_ORDER.map((messageType) => (
                        <label key={messageType}>
                          <input
                            type="checkbox"
                            checked={selectedMessageTypes.includes(messageType)}
                            onChange={() => toggleMessageType(messageType)}
                          />
                          <span>{MESSAGE_TYPE_LABELS[messageType]}</span>
                        </label>
                      ))}
                    </fieldset>
                  )}
                </section>
              )}

              <div className="ai-assistant-messages">
                {loadingMessages ? (
                  <div className="ai-assistant-empty">加载消息中...</div>
                ) : messages.length === 0 ? (
                  <div className="ai-assistant-empty">开始对话吧</div>
                ) : (
                  messages.map((msg) => {
                    if (
                      !isAdmin &&
                      msg.role !== "human" &&
                      msg.role !== "ai"
                    ) {
                      return null;
                    }
                    const isUser = msg.role === "human";
                    const isInternal = msg.role === "system" || msg.role === "tool";
                    const displayContent = formatMessageContent(msg);
                    const reasoning = reasoningMap[msg.id];
                    const hasReasoning = Boolean(reasoning);
                    const isFailed =
                      msg.role === "ai" &&
                      !msg.streaming &&
                      (msg.content === "（响应失败）" ||
                        msg.content === "（创建会话失败）");
                    const isThinking =
                      msg.role === "ai" && msg.streaming && !msg.reasoningComplete;

                    return (
                      <div
                        key={msg.id}
                        className={`ai-assistant-message ${
                          isUser ? "user" : isInternal ? "internal" : "ai"
                        }`}
                      >
                        <div className="ai-message-avatar">
                          {isUser ? <User size={16} /> : <Bot size={16} />}
                        </div>
                        <div className="ai-message-content">
                          {isAdmin && (
                            <div
                              className={`ai-message-role ai-message-role--${msg.role}`}
                            >
                              {MESSAGE_TYPE_LABELS[msg.role]}
                              {msg.name ? ` · ${msg.name}` : ""}
                            </div>
                          )}
                          {!isUser && (hasReasoning || isThinking) && (
                            <div className="ai-thinking-panel">
                              <button
                                type="button"
                                className="ai-thinking-indicator"
                                onClick={() => toggleReasoning(msg.id)}
                                aria-expanded={Boolean(showReasoning[msg.id])}
                              >
                                <span
                                  className={`ai-thinking-indicator__dot ${isThinking ? "ai-thinking-indicator__dot--pulse" : ""}`}
                                />
                                <span>{isThinking ? "深度思考中..." : "已深度思考"}</span>
                                <span style={{ marginLeft: 2 }}>
                                  {showReasoning[msg.id] ? (
                                    <ChevronRight size={13} style={{ transform: "rotate(90deg)" }} />
                                  ) : (
                                    <ChevronRight size={13} />
                                  )}
                                </span>
                              </button>
                              {showReasoning[msg.id] && (
                                <div className="ai-thinking-body">{reasoning}</div>
                              )}
                            </div>
                          )}

                          {displayContent !== "" && (
                            <div className="ai-message-bubble">
                              {displayContent}
                              {msg.streaming && (
                                <span className="ai-message-cursor" />
                              )}
                            </div>
                          )}

                          <div className="ai-message-footer">
                            <span className="ai-message-time">
                              {formatRelativeTime(msg.createdAt)}
                            </span>
                            {isFailed && (
                              <button
                                type="button"
                                className="ai-message-retry"
                                onClick={() => void handleRetry(msg.id)}
                                disabled={isStreaming}
                              >
                                <RefreshCw size={11} />
                                重试
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="ai-assistant-input-area">
                <textarea
                  ref={inputRef}
                  className="ai-assistant-input"
                  rows={1}
                  placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isStreaming}
                />
                <button
                  type="button"
                  className="ai-assistant-send-btn"
                  onClick={() => void handleSend()}
                  disabled={!input.trim() || isStreaming}
                  aria-label="发送消息"
                >
                  <Send size={18} />
                </button>
              </div>
            </>
          )}
        </main>
      </div>

      <ConfirmDeleteModal
        open={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDeleteConfirm()}
        itemType="会话"
        itemName={deleteTarget?.title ?? ""}
        description="删除后无法恢复，消息记录也将被清除。"
      />
    </div>
  );
};
