import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";

const BLURB = {
  admin: "You can manage staff accounts now. Catalog, discounts, billing and the finance dashboard arrive in the next phases.",
  staff: "Subscriptions, billing and payments will appear here as they are built. Staff accounts are created by an admin.",
  customer: "Your subscriptions and invoices will appear here. You only ever see your own data.",
} as const;

export default function Home() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Welcome{user.name ? `, ${user.name}` : ""}</h1>
      <p className="text-slate-600">{BLURB[user.role]}</p>
      <p className="flex gap-4 text-sm">
        {user.role === "admin" && <Link className="text-indigo-700" to="/staff">Manage staff</Link>}
        <Link className="text-indigo-700" to="/profile">Edit profile</Link>
      </p>
    </div>
  );
}
