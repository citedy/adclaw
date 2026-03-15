import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

interface PageHeaderProps {
  className?: string;
}

export function PageHeader({ className }: PageHeaderProps) {
  const { t } = useTranslation();

  return (
    <section className={`${styles.section} ${className || ""}`}>
      <h2 className={styles.sectionTitle}>{t("environments.title")}</h2>
      <p className={styles.sectionDesc}>{t("environments.description")}</p>
    </section>
  );
}
