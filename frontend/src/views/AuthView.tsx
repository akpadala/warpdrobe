import { useState, type FormEvent } from "react";
import { post } from "../api";
import type { Me } from "../types";

export default function AuthView({ onAuthed }: { onAuthed: (token: string, me: Me) => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = mode === "register" ? { email, name, password } : { email, password };
      const res = await post<{ token: string; user: Me }>(`/api/auth/${mode}`, body);
      onAuthed(res.token, res.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <h1 className="brand big">
          warp<b>drobe</b>
        </h1>
        <p>Skip the “what do I wear” loop. Outfits planned around your calendar and the weather.</p>
      </div>
      <form className="card auth-card" onSubmit={submit}>
        <div className="seg" role="tablist">
          <button type="button" className={mode === "register" ? "on" : ""} onClick={() => setMode("register")}>
            Create account
          </button>
          <button type="button" className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>
            Sign in
          </button>
        </div>
        {mode === "register" && (
          <label>
            First name
            <input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="given-name" />
          </label>
        )}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? "…" : mode === "register" ? "Start my closet" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
