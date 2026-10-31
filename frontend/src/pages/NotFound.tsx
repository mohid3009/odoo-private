import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="py-10">
      <h1 className="text-xl font-semibold">404 — page not found</h1>
      <Link className="mt-4 inline-block text-indigo-700" to="/">Back to home</Link>
    </div>
  );
}
