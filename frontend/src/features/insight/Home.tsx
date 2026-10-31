import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";

const BLURB = {
  admin: "Run the business: catalog, discounts, staff accounts, notifications, plus everything staff can do. The dashboard shows MRR, revenue and overdue invoices.",
  staff: "Manage subscriptions, run billing, confirm invoices and record payments. The dashboard shows MRR, revenue and overdue invoices.",
  customer: "Your subscriptions, invoices and payments, with a printable copy of every invoice. You only ever see your own data.",
} as const;

export default function Home() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Welcome{user.name ? `, ${user.name}` : ""}</h1>
      <p className="text-slate-600">{BLURB[user.role]}</p>
      <p className="flex gap-4 text-sm">
        {user.role !== "customer" && <Link className="text-indigo-700" to="/dashboard">Dashboard</Link>}
        {user.role !== "customer" && <Link className="text-indigo-700" to="/catalog">Catalog</Link>}
        {user.role === "customer" && <Link className="text-indigo-700" to="/my-invoices">My invoices</Link>}
        {user.role === "admin" && <Link className="text-indigo-700" to="/staff">Manage staff</Link>}
        <Link className="text-indigo-700" to="/profile">Edit profile</Link>
      </p>
    </div>
  );
}
