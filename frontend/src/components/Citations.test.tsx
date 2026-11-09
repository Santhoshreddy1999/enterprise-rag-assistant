import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Citation } from "../api/types";
import { Citations, renderContentWithCitations } from "./Citations";

const citation: Citation = {
  index: 1,
  document_id: "document-1",
  filename: "benefits-handbook.pdf",
  chunk_id: "chunk-1",
  page: 4,
  excerpt: "Employees receive twenty-five annual leave days.",
};

describe("citations", () => {
  it("renders a verified marker only for a known citation", () => {
    render(
      <p>
        {renderContentWithCitations(
          "The allowance is twenty-five days [1], not thirty [2].",
          [citation],
          "message-1",
        )}
      </p>,
    );

    expect(screen.getByRole("link", { name: "Jump to source 1" })).toHaveAttribute(
      "href",
      "#citation-message-1-1",
    );
    expect(screen.queryByRole("link", { name: "Jump to source 2" })).toBeNull();
    expect(screen.getByText("[2]", { exact: false })).toBeVisible();
  });

  it("shows source provenance and page information", () => {
    render(<Citations citations={[citation]} messageId="message-1" />);

    expect(screen.getByText("1 source")).toBeVisible();
    expect(screen.getByText("benefits-handbook.pdf")).toBeVisible();
    expect(screen.getByText("Page 4")).toBeVisible();
    expect(
      screen.getByText("Employees receive twenty-five annual leave days."),
    ).toBeVisible();
  });

  it("renders no disclosure when an answer has no sources", () => {
    const { container } = render(
      <Citations citations={[]} messageId="message-without-sources" />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
