import { useState } from "react";
import { api } from "../api.js";
import Logo from "./Logo.jsx";

export default function Login({ onLogin }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const username = name.trim();
    if (!/^[a-zA-Z0-9_]{2,30}$/.test(username)) {
      setError("Use 2–30 letters, numbers, or underscores.");
      return;
    }
    try {
      setError("");
      const user = await api("/login", "POST", { username });
      localStorage.setItem("delta_user", user.username);
      onLogin(user.username);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="login-page">
      <form className="card login" onSubmit={submit}>
        <div className="brand"><Logo />Delta</div>
        <p className="muted">
          A watchlist that tells you what changed while you were away.
        </p>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="pick a username"
          aria-label="username"
          autoComplete="username"
          maxLength={30}
          pattern="[a-zA-Z0-9_]+"
          autoFocus
        />
        <button type="submit" disabled={name.trim().length < 2}>
          Start watching
        </button>
        {error && <p className="error-text" role="alert">{error}</p>}
      </form>
    </div>
  );
}
