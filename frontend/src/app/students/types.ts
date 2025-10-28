export type StudentFilters = {
  course?: string | null;
  status?: string | null;
  deadline_before?: string | null;
  deadline_after?: string | null;
  min_hours?: string | null;
  max_hours?: string | null;
  rule?: string | null;
};

export type NonComplianceStudent = {
  id: number;
  status: string;
  progress_hours: number;
  last_notified_at: string | null;
  deadline_date: string | null;
  hours_required: number | null;
  student: {
    id: number;
    full_name: string;
    email: string;
    certificate_expires_at: string | null;
  };
  course: {
    id: number;
    name: string;
    deadline_date: string | null;
    hours_required: number | null;
  } | null;
  rule_results: Record<string, boolean>;
  violations: string[];
};

export type NonComplianceResponse = {
  total: number;
  items: NonComplianceStudent[];
};
