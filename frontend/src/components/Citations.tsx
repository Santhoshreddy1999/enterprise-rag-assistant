import type { ReactNode } from "react";
import type { Citation } from "../api/types";
import { Icon } from "./Icon";

export function renderContentWithCitations(
  content: string,
  citations: Citation[],
  messageId: string,
): ReactNode {
  if (citations.length === 0) {
    return content;
  }

  const knownIndexes = new Set(citations.map((citation) => citation.index));
  return content.split(/(\[\d+\])/g).map((part, position) => {
    const match = /^\[(\d+)\]$/.exec(part);
    if (!match) {
      return part;
    }
    const index = Number(match[1]);
    if (!knownIndexes.has(index)) {
      return part;
    }

    return (
      <a
        aria-label={`Jump to source ${index}`}
        className="citation-marker"
        href={`#citation-${messageId}-${index}`}
        key={`${part}-${position}`}
      >
        {index}
      </a>
    );
  });
}

export function Citations({
  citations,
  messageId,
}: {
  citations: Citation[];
  messageId: string;
}) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <details className="citations" open>
      <summary>
        <span>
          <Icon name="quote" size={15} />
          {citations.length} {citations.length === 1 ? "source" : "sources"}
        </span>
        <Icon className="citations__chevron" name="chevron" size={15} />
      </summary>
      <ol className="citation-list">
        {citations.map((citation) => (
          <li
            className="citation-card"
            id={`citation-${messageId}-${citation.index}`}
            key={`${citation.chunk_id}-${citation.index}`}
            tabIndex={-1}
          >
            <div className="citation-card__head">
              <span className="citation-card__index">{citation.index}</span>
              <div>
                <strong>{citation.filename}</strong>
                <span>
                  {citation.page ? `Page ${citation.page}` : "Document excerpt"}
                </span>
              </div>
            </div>
            <blockquote>{citation.excerpt}</blockquote>
          </li>
        ))}
      </ol>
    </details>
  );
}
