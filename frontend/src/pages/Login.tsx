import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // In Phase 1 full auth will be wired to /api/auth/login
    alert("Brightloop Auth: Ready for Phase 1 credentials.");
  };

  return (
    <div className="min-h-screen bg-[#070709] text-[#C8C8D0] p-4 sm:p-8 flex items-center justify-center">
      <div className="relative w-full max-w-md rounded-[24px] border border-white/[0.08] bg-[#0B0B0D] p-8 sm:p-10 shadow-[0_24px_80px_-20px_rgba(0,0,0,0.95)]">
        {/* Nav back */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs font-mono text-[#8A8A94] hover:text-white mb-8 transition-colors"
        >
          ← Back to Brightloop
        </Link>

        {/* Brand */}
        <div className="flex items-center gap-2.5 mb-6">
          <span className="w-2.5 h-2.5 rounded-full bg-gradient-to-tr from-[#9A9AA3] via-white to-[#E4E4EB] shadow-[0_0_8px_rgba(255,255,255,0.7)]" />
          <h1 className="text-2xl font-bold tracking-tight text-white">Log in to Brightloop</h1>
        </div>

        <p className="text-sm text-[#8A8A94] mb-8">
          Enter your credentials to access your billing workspace and customer portal.
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium uppercase tracking-wider text-[#9A9AA3] mb-2">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@brightloop.io"
              className="w-full rounded-xl border border-white/[0.08] bg-[#121216] px-4 py-3 text-sm text-white placeholder-[#5A5A62] focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/30"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-medium uppercase tracking-wider text-[#9A9AA3]">
                Password
              </label>
              <a href="#" className="text-xs text-[#8A8A94] hover:text-white transition-colors">
                Forgot?
              </a>
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full rounded-xl border border-white/[0.08] bg-[#121216] px-4 py-3 text-sm text-white placeholder-[#5A5A62] focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/30"
            />
          </div>

          <button
            type="submit"
            className="w-full mt-2 py-3.5 rounded-full bg-gradient-to-r from-white via-[#F4F4F6] to-[#E2E2E8] text-[#0B0B0D] font-semibold text-sm shadow-[0_0_24px_rgba(255,255,255,0.2)] hover:shadow-[0_0_36px_rgba(255,255,255,0.4)] transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-white"
          >
            Sign In ↗
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-white/[0.06] text-center text-xs text-[#8A8A94]">
          Protected by role-based access control and Odoo identity sync.
        </div>
      </div>
    </div>
  );
}

