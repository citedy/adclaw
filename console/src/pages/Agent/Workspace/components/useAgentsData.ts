import { useState, useEffect } from "react";
import { message } from "@agentscope-ai/design";
import api from "../../../../api";
import type { MarkdownFile, DailyMemoryFile } from "../../../../api/types";

export const useAgentsData = () => {
  const [files, setFiles] = useState<MarkdownFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<MarkdownFile | null>(null);
  const [dailyMemories, setDailyMemories] = useState<DailyMemoryFile[]>([]);
  const [expandedMemory, setExpandedMemory] = useState(false);
  const [fileContent, setFileContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [workspacePath, setWorkspacePath] = useState("");

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const fileList = await api.listFiles();
      setFiles(fileList as MarkdownFile[]);
      if (fileList.length > 0) {
        const path = fileList[0].path;
        const workspace = path.substring(
          0,
          path.lastIndexOf("/") || path.lastIndexOf("\\"),
        );
        setWorkspacePath(workspace);
      }
    } catch (error) {
      console.error("Failed to fetch files", error);
      message.error("Failed to load file list");
    }
  };

  const fetchDailyMemories = async () => {
    try {
      const memoryList = await api.listDailyMemory();
      setDailyMemories(memoryList);
    } catch (error) {
      console.error("Failed to fetch daily memories", error);
      message.error("Failed to load memory list");
    }
  };

  const handleFileClick = async (file: MarkdownFile) => {
    if (file.filename === "MEMORY.md") {
      if (expandedMemory && selectedFile?.filename === "MEMORY.md") {
        setExpandedMemory(false);
        return;
      } else {
        setExpandedMemory(true);
        fetchDailyMemories();
      }
    }

    setSelectedFile(file);
    setLoading(true);
    try {
      const data = await api.loadFile(file.filename);
      setFileContent(data.content);
      setOriginalContent(data.content);
    } catch (error) {
      console.error("Failed to load file", error);
      message.error("Failed to load file");
    } finally {
      setLoading(false);
    }
  };

  const handleDailyMemoryClick = async (daily: DailyMemoryFile) => {
    setSelectedFile({
      filename: `${daily.date}.md`,
      path: daily.path,
      size: daily.size,
      created_time: daily.created_time,
      modified_time: daily.modified_time,
      updated_at: daily.updated_at,
    });
    setLoading(true);
    try {
      const data = await api.loadDailyMemory(daily.date);
      setFileContent(data.content);
      setOriginalContent(data.content);
    } catch (error) {
      console.error("Failed to load daily memory", error);
      message.error("Failed to load daily memory");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedFile) return;
    setLoading(true);
    try {
      if (selectedFile.filename.match(/^\d{4}-\d{2}-\d{2}\.md$/)) {
        const date = selectedFile.filename.replace(".md", "");
        await api.saveDailyMemory(date, fileContent);
      } else {
        await api.saveFile(selectedFile.filename, fileContent);
      }
      setOriginalContent(fileContent);
      message.success("Saved successfully");
      if (selectedFile.filename.match(/^\d{4}-\d{2}-\d{2}\.md$/)) {
        fetchDailyMemories();
      } else {
        fetchFiles();
      }
    } catch (error) {
      console.error("Failed to save file", error);
      message.error("Failed to save");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFileContent(originalContent);
  };

  const hasChanges = fileContent !== originalContent;

  return {
    files,
    selectedFile,
    dailyMemories,
    expandedMemory,
    fileContent,
    loading,
    workspacePath,
    hasChanges,
    setFileContent,
    fetchFiles,
    fetchDailyMemories,
    handleFileClick,
    handleDailyMemoryClick,
    handleSave,
    handleReset,
  };
};
