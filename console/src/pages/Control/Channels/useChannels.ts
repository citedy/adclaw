import { useState, useEffect } from "react";
import api from "../../../api";
import type { ChannelConfig } from "../../../api/types";

export function useChannels() {
  const [channels, setChannels] = useState<ChannelConfig>({} as ChannelConfig);
  const [loading, setLoading] = useState(true);

  const fetchChannels = async () => {
    setLoading(true);
    try {
      const data = await api.listChannels();
      if (data) {
        setChannels(data);
      }
    } catch (error) {
      console.error("❌ Failed to load channels:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      await fetchChannels();
    };

    if (mounted) {
      fetchData();
    }

    return () => {
      mounted = false;
    };
  }, []);

  return {
    channels,
    loading,
    fetchChannels,
  };
}
