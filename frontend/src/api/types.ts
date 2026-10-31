export type Role = "admin" | "staff" | "customer";

export interface Profile {
  company_name: string;
  phone: string;
  address: string;
  whatsapp_number: string;
  whatsapp_opt_in: boolean;
  email_notifications: boolean;
  whatsapp_opted_in_at: string | null;
  odoo_sync_status: string;
}

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  profile: Profile | null;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
