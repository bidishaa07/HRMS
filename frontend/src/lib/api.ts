const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && path !== "/auth/refresh" && path !== "/auth/login") {
    const refreshed = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
    if (refreshed.ok) response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" })) as { detail?: string | Array<{ msg: string }> };
    const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join(", ") : body.detail;
    throw new ApiError(response.status, detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type User = {
  id: string; email: string; login_id: string; name: string; company_name: string; phone?: string;
  role: "employee" | "hr" | "admin"; oauth_provider?: string; employee_id: string; employee_code: string;
};
export type Summary = { employees: number; present_today: number; on_leave: number; pending_approvals: number; payroll_total: number; organization_health: number; burnout_alerts: number; late_arrivals: number };
export type Employee = { id: string; user_id: string; employee_code: string; name: string; email: string; phone: string; role: string; department: string; title: string; location: string; joining_date: string; profile_completion: number; health_score: number; salary: number; status: string; check_in?: string; check_out?: string };
export type Attendance = { id: string; employee_id: string; employee_name: string; date: string; check_in?: string; check_out?: string; status: string; work_minutes: number; extra_minutes: number };
export type Leave = { id: string; employee_id: string; employee_name: string; leave_type: string; start_date: string; end_date: string; remarks: string; status: string; comment?: string; days: number };
export type Payroll = { id: string; employee_name: string; period: string; basic: number; bonuses: number; deductions: number; net_salary: number; components: Record<string, number> };
export type Department = { id: string; name: string; description: string; employees: number };
export type DocumentItem = { id: string; name: string; document_type: string; mime_type?: string; download_url?: string };
export type Notification = { id: string; title: string; body: string; read: boolean; created_at: string };
export type AgentInfo = { name: string; purpose: string; tools: string[]; status: string; success_rate: number; tasks_today: number };
export type AgentReply = { message: string; agent: string; tools_used: string[]; explainability: string; task_id: string };

export const api = {
  register: (body: { company_name: string; name: string; email: string; phone: string; password: string; confirm_password: string }) => request<{ user: User }>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { login: string; password: string; role?: "admin" | "employee" }) => request<{ user: User }>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
  updateProfile: (body: { name: string; phone: string }) => request<User>("/auth/me", { method: "PATCH", body: JSON.stringify(body) }),
  changePassword: (body: { current_password: string; new_password: string }) => request<void>("/auth/change-password", { method: "POST", body: JSON.stringify(body) }),
  providerStatus: () => request<{ google: boolean }>("/auth/providers"),
  oauthStart: (provider: "google") => request<{ authorization_url: string }>(`/auth/oauth/${provider}/start`),
  summary: () => request<Summary>("/dashboard/summary"),
  employees: (search = "") => request<Employee[]>(`/employees?search=${encodeURIComponent(search)}`),
  createEmployee: (body: { name: string; email: string; phone: string; department: string; title: string; salary: number; joining_date: string }) => request<Employee & { temporary_password: string }>("/employees", { method: "POST", body: JSON.stringify(body) }),
  attendance: (month?: string) => request<Attendance[]>(`/attendance${month ? `?month=${month}` : ""}`),
  checkIn: () => request<{ message: string; check_in: string; status: string }>("/attendance/check-in", { method: "POST" }),
  checkOut: () => request<{ message: string; check_out: string; work_minutes: number }>("/attendance/check-out", { method: "POST" }),
  leaves: () => request<Leave[]>("/leaves"),
  applyLeave: (body: { leave_type: string; start_date: string; end_date: string; remarks: string }) => request<Leave>("/leaves", { method: "POST", body: JSON.stringify(body) }),
  decideLeave: (id: string, decision: "approved" | "rejected", comment = "") => request<Leave>(`/leaves/${id}`, { method: "PATCH", body: JSON.stringify({ decision, comment }) }),
  payroll: () => request<Payroll[]>("/payroll"),
  payrollDocxUrl: (id: string) => `${API_URL}/payroll/${id}/payslip.docx`,
  departments: () => request<Department[]>("/departments"),
  documents: () => request<DocumentItem[]>("/documents"),
  document: (id: string) => request<DocumentItem>(`/documents/${id}`),
  documentDownloadUrl: (id: string) => `${API_URL}/documents/${id}/download`,
  uploadDocument: (form: FormData) => request<DocumentItem>("/documents", { method: "POST", body: form }),
  notifications: () => request<Notification[]>("/notifications"),
  readNotification: (id: string) => request<{ read: boolean }>(`/notifications/${id}/read`, { method: "PATCH" }),
  agents: () => request<AgentInfo[]>("/agents"),
  runAgentCommand: (command: string) => request<AgentReply>("/agents/command", { method: "POST", body: JSON.stringify({ command }) }),
};
