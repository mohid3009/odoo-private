import { Link } from "react-router-dom";

export default function Forbidden() {
  return (
    <div className="py-10">
      <h1 className="text-xl font-semibold">403 — not allowed</h1>
      <p className="mt-2 text-slate-600">Your role cannot open this page.</p>
      <Link className="mt-4 inline-block text-sky-700" to="/">Back to home</Link>
    </div>
  );
}
