import { Card } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import type { SingleChannelConfig } from "../../../../api/types";
import { CHANNEL_LABELS, type ChannelKey } from "./constants";
import styles from "../index.module.less";

interface ChannelCardProps {
  channelKey: ChannelKey;
  config: SingleChannelConfig;
  isHover: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function ChannelCard({
  channelKey,
  config,
  isHover,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: ChannelCardProps) {
  const { t } = useTranslation();
  const enabled = Boolean((config as SingleChannelConfig).enabled);

  const getCardClassNames = () => {
    if (isHover) return `${styles.channelCard} ${styles.hover}`;
    if (enabled) return `${styles.channelCard} ${styles.enabled}`;
    return `${styles.channelCard} ${styles.normal}`;
  };

  return (
    <Card
      hoverable
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={getCardClassNames()}
      bodyStyle={{ padding: 20 }}
    >
      <div className={styles.cardHeader}>
        <span className={styles.statusContainer}>
          <span
            className={`${styles.statusDot} ${
              enabled ? styles.enabled : styles.disabled
            }`}
          />
          {enabled ? t("common.enabled") : t("common.disabled")}
        </span>
        <span className={styles.channelTag}>{CHANNEL_LABELS[channelKey]}</span>
      </div>

      <div className={styles.cardTitle}>{CHANNEL_LABELS[channelKey]}</div>
      <div className={styles.cardDescription}>
        {t("channels.botPrefix")}:{" "}
        {(config as SingleChannelConfig).bot_prefix || t("channels.notSet")}
      </div>

      <div className={styles.cardHint}>{t("channels.clickCardToEdit")}</div>
    </Card>
  );
}
