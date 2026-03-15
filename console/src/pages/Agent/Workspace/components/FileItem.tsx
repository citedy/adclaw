import React from "react";
import type { MarkdownFile, DailyMemoryFile } from "../../../../api/types";
import { formatFileSize, formatTimeAgo } from "./utils";
import styles from "../index.module.less";

interface FileItemProps {
  file: MarkdownFile;
  selectedFile: MarkdownFile | null;
  expandedMemory: boolean;
  dailyMemories: DailyMemoryFile[];
  onFileClick: (file: MarkdownFile) => void;
  onDailyMemoryClick: (daily: DailyMemoryFile) => void;
}

export const FileItem: React.FC<FileItemProps> = ({
  file,
  selectedFile,
  expandedMemory,
  dailyMemories,
  onFileClick,
  onDailyMemoryClick,
}) => {
  const isSelected = selectedFile?.filename === file.filename;
  const isMemoryFile = file.filename === "MEMORY.md";

  return (
    <div>
      <div
        onClick={() => onFileClick(file)}
        className={`${styles.fileItem} ${isSelected ? styles.selected : ""}`}
      >
        <div className={styles.fileItemHeader}>
          <div className={styles.fileInfo}>
            <div className={styles.fileItemName}>{file.filename}</div>
            <div className={styles.fileItemMeta}>
              {formatFileSize(file.size)} · {formatTimeAgo(file.updated_at)}
            </div>
          </div>
          {isMemoryFile && (
            <span className={styles.expandIcon}>
              {expandedMemory ? "▼" : "▶"}
            </span>
          )}
        </div>
      </div>

      {isMemoryFile && expandedMemory && (
        <div className={styles.dailyMemoryList}>
          {dailyMemories.map((daily) => {
            const isDailySelected =
              selectedFile?.filename === `${daily.date}.md`;
            return (
              <div
                key={daily.date}
                onClick={() => onDailyMemoryClick(daily)}
                className={`${styles.dailyMemoryItem} ${
                  isDailySelected ? styles.selected : ""
                }`}
              >
                <div className={styles.dailyMemoryName}>{daily.date}.md</div>
                <div className={styles.dailyMemoryMeta}>
                  {formatFileSize(daily.size)} ·{" "}
                  {formatTimeAgo(daily.updated_at)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
