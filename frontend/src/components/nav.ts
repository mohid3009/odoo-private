import type { Role } from "../api/types";

// Each feature folder exports its own NavItem[]; Layout merges them so nobody edits another team's list.
export interface NavItem {
  to: string;
  label: string;
  roles: Role[];
  end?: boolean;
}
