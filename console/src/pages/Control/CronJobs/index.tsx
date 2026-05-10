import { useState } from "react";
import { Button, Card, Form, Modal, Table } from "@agentscope-ai/design";
import dayjs from "dayjs";
import type { CronJobSpecOutput } from "../../../api/types";
import { useTranslation } from "react-i18next";
import {
  createColumns,
  JobDrawer,
  useCronJobs,
  DEFAULT_FORM_VALUES,
} from "./components";
import { parseCron, serializeCron } from "./components/parseCron";
import styles from "./index.module.less";

type CronJob = CronJobSpecOutput;

function CronJobsEmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className={styles.emptyState}>
      <div className={styles.emptyStateCore}>
        <div className={styles.emptyStateIcon} />
        <h3 className={styles.emptyStateTitle}>{title}</h3>
        <p className={styles.emptyStateDescription}>{description}</p>
      </div>
    </div>
  );
}

function CronJobsPage() {
  const { t } = useTranslation();
  const {
    jobs,
    loading,
    createJob,
    updateJob,
    deleteJob,
    toggleEnabled,
    executeNow,
  } = useCronJobs();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingJob, setEditingJob] = useState<CronJob | null>(null);
  const [form] = Form.useForm<CronJob>();
  const hasJobs = jobs.length > 0;
  const showTable = loading || hasJobs;

  const handleCreate = () => {
    setEditingJob(null);
    form.resetFields();
    form.setFieldsValue(DEFAULT_FORM_VALUES);
    setDrawerOpen(true);
  };

  const handleEdit = (job: CronJob) => {
    setEditingJob(job);

    // Parse cron expression to form fields
    const cronParts = parseCron(job.schedule?.cron || "0 9 * * *");

    const formValues: any = {
      ...job,
      request: {
        ...job.request,
        input: job.request?.input
          ? JSON.stringify(job.request.input, null, 2)
          : "",
      },
      cronType: cronParts.type,
    };

    // Set time picker value
    if (cronParts.type === "daily" || cronParts.type === "weekly") {
      const h = cronParts.hour ?? 9;
      const m = cronParts.minute ?? 0;
      formValues.cronTime = dayjs().hour(h).minute(m);
    }

    // Set days of week
    if (cronParts.type === "weekly" && cronParts.daysOfWeek) {
      formValues.cronDaysOfWeek = cronParts.daysOfWeek;
    }

    // Set custom cron
    if (cronParts.type === "custom" && cronParts.rawCron) {
      formValues.cronCustom = cronParts.rawCron;
    }

    form.setFieldsValue(formValues);
    setDrawerOpen(true);
  };

  const handleDelete = (jobId: string) => {
    Modal.confirm({
      title: t("cronJobs.confirmDelete"),
      content: t("cronJobs.deleteConfirm"),
      okText: t("cronJobs.deleteText"),
      okType: "primary",
      cancelText: t("cronJobs.cancelText"),
      onOk: async () => {
        await deleteJob(jobId);
      },
    });
  };

  const handleToggleEnabled = async (job: CronJob) => {
    await toggleEnabled(job);
  };

  const handleExecuteNow = async (job: CronJob) => {
    Modal.confirm({
      title: t("cronJobs.executeNowTitle"),
      content: t("cronJobs.executeNowContent", { name: job.name }),
      okText: t("cronJobs.executeNowConfirm"),
      okType: "primary",
      cancelText: t("cronJobs.cancelText"),
      onOk: async () => {
        await executeNow(job.id);
      },
    });
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingJob(null);
  };

  const handleSubmit = async (values: any) => {
    // Serialize cron from form fields
    const cronParts: any = {
      type: values.cronType || "daily",
    };

    if (values.cronType === "daily" || values.cronType === "weekly") {
      if (values.cronTime) {
        cronParts.hour = values.cronTime.hour();
        cronParts.minute = values.cronTime.minute();
      }
    }

    if (values.cronType === "weekly" && values.cronDaysOfWeek) {
      cronParts.daysOfWeek = values.cronDaysOfWeek;
    }

    if (values.cronType === "custom" && values.cronCustom) {
      cronParts.rawCron = values.cronCustom;
    }

    const cronExpression = serializeCron(cronParts);

    let processedValues = {
      ...values,
      schedule: {
        ...values.schedule,
        cron: cronExpression,
      },
    };

    // Parse request input JSON
    if (values.request?.input && typeof values.request.input === "string") {
      try {
        processedValues = {
          ...processedValues,
          request: {
            ...values.request,
            input: JSON.parse(values.request.input as any),
          },
        };
      } catch (error) {
        console.error("❌ Failed to parse request.input JSON:", error);
      }
    }

    let success = false;
    if (editingJob) {
      success = await updateJob(editingJob.id, processedValues);
    } else {
      success = await createJob(processedValues);
    }
    if (success) {
      setDrawerOpen(false);
    }
  };

  const columns = createColumns({
    onToggleEnabled: handleToggleEnabled,
    onExecuteNow: handleExecuteNow,
    onEdit: handleEdit,
    onDelete: handleDelete,
    t,
  });

  return (
    <div className={styles.cronJobsPage}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>{t("cronJobs.title")}</h1>
          <p className={styles.description}>{t("cronJobs.description")}</p>
        </div>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.toolbarMeta}>
          <div className={styles.countChip}>
            {t("cronJobs.totalItems", { count: jobs.length })}
          </div>
        </div>
        <Button type="primary" onClick={handleCreate}>
          + {t("cronJobs.createJob")}
        </Button>
      </div>

      <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
        <div className={styles.surfaceHead}>
          <div className={styles.surfaceTitle}>
            <strong>{t("cronJobs.registryTitle")}</strong>
            <span>{t("cronJobs.registrySubtitle")}</span>
          </div>
        </div>

        {showTable ? (
          <Table
            className={styles.cronJobsTable}
            columns={columns}
            dataSource={jobs}
            loading={loading}
            rowKey="id"
            scroll={{ x: 2840 }}
            pagination={{
              pageSize: 10,
              showSizeChanger: false,
              showTotal: (total) => t("cronJobs.totalItems", { count: total }),
            }}
          />
        ) : (
          <div className={styles.emptyStatePanel}>
            <CronJobsEmptyState
              title={t("cronJobs.emptyTitle")}
              description={t("cronJobs.emptyDescription")}
            />
          </div>
        )}
      </Card>

      <JobDrawer
        open={drawerOpen}
        editingJob={editingJob}
        form={form}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default CronJobsPage;
