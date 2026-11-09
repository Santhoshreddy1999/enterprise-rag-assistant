import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
} from "react";
import { api } from "../api/client";
import type { DocumentRecord } from "../api/types";
import { EmptyState, ErrorState, Spinner, StatusMessage } from "./Feedback";
import { Icon } from "./Icon";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(["txt", "md", "pdf", "docx"]);

function fileExtension(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "";
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function validateFile(file: File): string | null {
  if (!ALLOWED_EXTENSIONS.has(fileExtension(file.name))) {
    return "Choose a TXT, Markdown, PDF, or DOCX file.";
  }
  if (file.size === 0) {
    return "Empty documents cannot be uploaded.";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "That file is larger than the 10 MiB upload limit.";
  }
  return null;
}

function DocumentSkeleton() {
  return (
    <div aria-label="Loading documents" className="document-skeleton" role="status">
      {[0, 1, 2].map((item) => (
        <div className="skeleton-row" key={item}>
          <span className="skeleton skeleton--icon" />
          <span className="skeleton skeleton--text" />
        </div>
      ))}
    </div>
  );
}

export function DocumentPanel() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);

    void api
      .listDocuments(controller.signal)
      .then(setDocuments)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setLoadError(
          reason instanceof Error ? reason.message : "Unable to load documents.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (confirmingId) {
      confirmRef.current?.focus();
    }
  }, [confirmingId]);

  function chooseFile(file: File | undefined) {
    setNotice(null);
    setFileError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const error = validateFile(file);
    if (error) {
      setSelectedFile(null);
      setFileError(error);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
      return;
    }
    setSelectedFile(file);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || uploading) {
      return;
    }

    setUploading(true);
    setFileError(null);
    setNotice(null);
    try {
      const document = await api.uploadDocument(selectedFile);
      setDocuments((current) => [document, ...current]);
      setNotice(`${document.filename} is ready in your library.`);
      setSelectedFile(null);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    } catch (reason) {
      setFileError(
        reason instanceof Error ? reason.message : "Unable to upload this file.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(document: DocumentRecord) {
    setDeletingId(document.id);
    setDeleteError(null);
    try {
      await api.deleteDocument(document.id);
      setDocuments((current) =>
        current.filter((candidate) => candidate.id !== document.id),
      );
      setConfirmingId(null);
      setNotice(`${document.filename} was removed.`);
    } catch (reason) {
      setDeleteError(
        reason instanceof Error ? reason.message : "Unable to delete this document.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="library-panel" aria-labelledby="library-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Knowledge base</p>
          <h2 id="library-title">Documents</h2>
        </div>
        {!loading && !loadError ? (
          <span className="count-badge" aria-label={`${documents.length} documents`}>
            {documents.length}
          </span>
        ) : null}
      </div>

      <form className="upload-form" onSubmit={handleUpload}>
        <label
          className={`upload-dropzone${dragging ? " is-dragging" : ""}`}
          onDragEnter={() => setDragging(true)}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <input
            accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="sr-only"
            disabled={uploading}
            onChange={handleFileChange}
            ref={inputRef}
            type="file"
          />
          <span className="upload-dropzone__icon">
            <Icon name="upload" size={20} />
          </span>
          <span>
            <strong>{selectedFile ? selectedFile.name : "Add a document"}</strong>
            <small>
              {selectedFile
                ? `${(selectedFile.size / 1024).toFixed(0)} KB selected`
                : "Drop a file or browse · 10 MiB max"}
            </small>
          </span>
        </label>
        <p className="upload-form__formats" id="file-formats">
          TXT, Markdown, PDF, and DOCX
        </p>

        {fileError ? (
          <p className="field-error" role="alert">
            {fileError}
          </p>
        ) : null}

        {selectedFile ? (
          <div className="upload-actions">
            <button
              className="button button--small button--primary"
              disabled={uploading}
              type="submit"
            >
              {uploading ? (
                <>
                  <Spinner label="Uploading document" />
                  Uploading…
                </>
              ) : (
                "Upload document"
              )}
            </button>
            <button
              className="button button--small button--ghost"
              disabled={uploading}
              onClick={() => chooseFile(undefined)}
              type="button"
            >
              Clear
            </button>
          </div>
        ) : null}
      </form>

      {notice ? (
        <StatusMessage onDismiss={() => setNotice(null)}>{notice}</StatusMessage>
      ) : null}

      <div className="document-list-wrap">
        {loading ? <DocumentSkeleton /> : null}
        {!loading && loadError ? (
          <ErrorState
            compact
            message={loadError}
            onRetry={() => setReloadKey((value) => value + 1)}
            title="Documents unavailable"
          />
        ) : null}
        {!loading && !loadError && documents.length === 0 ? (
          <EmptyState
            icon={<Icon name="file" size={22} />}
            title="Your library is empty"
          >
            Upload a document to start asking source-grounded questions.
          </EmptyState>
        ) : null}
        {!loading && !loadError && documents.length > 0 ? (
          <ul className="document-list">
            {documents.map((document) => {
              const isConfirming = confirmingId === document.id;
              const isDeleting = deletingId === document.id;
              return (
                <li className="document-item" key={document.id}>
                  <div className="document-item__main">
                    <span className="file-icon">
                      {fileExtension(document.filename).toUpperCase() || "FILE"}
                    </span>
                    <div className="document-item__copy">
                      <strong title={document.filename}>{document.filename}</strong>
                      <span>
                        {formatDate(document.created_at)}
                        {document.status === "ready"
                          ? ` · ${document.chunk_count} ${
                              document.chunk_count === 1 ? "passage" : "passages"
                            }`
                          : ""}
                      </span>
                    </div>
                    <span
                      className={`status-chip status-chip--${document.status.toLowerCase()}`}
                    >
                      {document.status}
                    </span>
                    <button
                      aria-expanded={isConfirming}
                      aria-label={`Delete ${document.filename}`}
                      className="icon-button document-item__delete"
                      disabled={isDeleting}
                      onClick={() => {
                        setDeleteError(null);
                        setConfirmingId(isConfirming ? null : document.id);
                      }}
                      type="button"
                    >
                      <Icon name="trash" size={16} />
                    </button>
                  </div>

                  {isConfirming ? (
                    <div className="delete-confirmation" role="alertdialog">
                      <p>
                        Delete <strong>{document.filename}</strong>? This cannot be
                        undone.
                      </p>
                      {deleteError ? (
                        <p className="field-error" role="alert">
                          {deleteError}
                        </p>
                      ) : null}
                      <div>
                        <button
                          className="button button--small button--danger"
                          disabled={isDeleting}
                          onClick={() => void deleteDocument(document)}
                          ref={confirmRef}
                          type="button"
                        >
                          {isDeleting ? "Deleting…" : "Delete"}
                        </button>
                        <button
                          className="button button--small button--ghost"
                          disabled={isDeleting}
                          onClick={() => setConfirmingId(null)}
                          type="button"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </section>
  );
}
