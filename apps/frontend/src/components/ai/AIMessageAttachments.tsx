import {
  ArrowUpRight,
  Check,
  Disc3,
  ListMusic,
  Music2,
  Play,
  X,
} from "lucide-react";

import type {
  AIConfirmationCardAttachment,
  AIConversationAttachment,
} from "../../shared/api/types";

type ResourceType = "music" | "playlist" | "album";

type Props = {
  attachments: AIConversationAttachment[];
  onOpen: (type: ResourceType, id: number) => void;
  onPlayMusic: (id: number) => void;
  onConfirm: (attachment: AIConfirmationCardAttachment) => void;
  onCancelConfirmation: (confirmationToken: string) => void;
  disabledConfirmationTokens?: Set<string>;
};

const EMPTY_CONFIRMATION_TOKENS = new Set<string>();

const Cover = ({
  url,
  type,
}: {
  url: string | null;
  type: ResourceType;
}) => {
  if (url) {
    return <img className="ai-resource-card__cover" src={url} alt="" />;
  }
  const Icon = type === "music" ? Music2 : type === "playlist" ? ListMusic : Disc3;
  return (
    <div className={`ai-resource-card__cover ai-resource-card__cover--${type}`}>
      <Icon size={20} aria-hidden="true" />
    </div>
  );
};

export function AIMessageAttachments({
  attachments,
  onOpen,
  onPlayMusic,
  onConfirm,
  onCancelConfirmation,
  disabledConfirmationTokens = EMPTY_CONFIRMATION_TOKENS,
}: Props) {
  return (
    <div className="ai-message-attachments">
      {attachments.map((attachment, attachmentIndex) => {
        if (attachment.type === "music_card") {
          return (
            <section
              className="ai-resource-group ai-resource-group--music"
              aria-label="推荐音乐"
              key={`music-${attachmentIndex}`}
            >
              {attachment.items.map((item) => (
                <article className="ai-resource-card ai-resource-card--music" key={item.id}>
                  <Cover url={item.cover_url} type="music" />
                  <div className="ai-resource-card__body">
                    <strong>{item.title}</strong>
                    <span>
                      {[item.authors.join(" / "), item.album].filter(Boolean).join(" · ")}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="ai-resource-card__play"
                    aria-label={`播放${item.title}`}
                    onClick={() => onPlayMusic(item.id)}
                  >
                    <Play size={15} fill="currentColor" />
                  </button>
                  <button
                    type="button"
                    className="ai-resource-card__open"
                    aria-label={`查看音乐${item.title}`}
                    onClick={() => onOpen("music", item.id)}
                  >
                    <ArrowUpRight size={16} />
                  </button>
                </article>
              ))}
            </section>
          );
        }

        if (attachment.type === "playlist_card") {
          return (
            <section
              className="ai-resource-group ai-resource-group--playlist"
              aria-label="推荐歌单"
              key={`playlist-${attachmentIndex}`}
            >
              {attachment.items.map((item) => (
                <button
                  type="button"
                  className="ai-resource-card ai-resource-card--playlist"
                  key={item.id}
                  onClick={() => onOpen("playlist", item.id)}
                  aria-label={`查看歌单${item.title}`}
                >
                  <Cover url={item.cover_url} type="playlist" />
                  <span className="ai-resource-card__body">
                    <strong>{item.title}</strong>
                    <span>歌单 · {item.music_count} 首</span>
                    <small>{item.creator}</small>
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              ))}
            </section>
          );
        }

        if (attachment.type === "album_card") {
          return (
            <section
              className="ai-resource-group ai-resource-group--album"
              aria-label="推荐专辑"
              key={`album-${attachmentIndex}`}
            >
              {attachment.items.map((item) => (
                <button
                  type="button"
                  className="ai-resource-card ai-resource-card--album"
                  key={item.id}
                  onClick={() => onOpen("album", item.id)}
                  aria-label={`查看专辑${item.title}`}
                >
                  <Cover url={item.cover_url} type="album" />
                  <span className="ai-resource-card__body">
                    <strong>{item.title}</strong>
                    <span>专辑 · {item.music_count} 首</span>
                    <small>{item.authors.join(" / ")}</small>
                  </span>
                  <Disc3 className="ai-resource-card__album-mark" size={24} />
                </button>
              ))}
            </section>
          );
        }

        const disabled = disabledConfirmationTokens.has(
          attachment.confirmation_token,
        );
        const actionLabel =
          attachment.action === "collect" ? "确认收藏" : "确认取消收藏";
        return (
          <section
            className="ai-confirmation-card"
            aria-label="操作确认"
            key={`confirmation-${attachment.confirmation_token}`}
          >
            <Cover
              url={attachment.resource.cover_url}
              type={attachment.resource_type}
            />
            <div className="ai-confirmation-card__body">
              <strong>{attachment.prompt}</strong>
              <span>此操作只会在你明确确认后执行。</span>
            </div>
            <div className="ai-confirmation-card__actions">
              <button
                type="button"
                className="ai-confirmation-card__cancel"
                onClick={() =>
                  onCancelConfirmation(attachment.confirmation_token)
                }
                disabled={disabled}
                aria-label="取消操作"
              >
                <X size={14} />
                取消
              </button>
              <button
                type="button"
                className="ai-confirmation-card__confirm"
                onClick={() => onConfirm(attachment)}
                disabled={disabled}
                aria-label={actionLabel}
              >
                <Check size={14} />
                {actionLabel}
              </button>
            </div>
          </section>
        );
      })}
    </div>
  );
}
