import React from "react";

type Props = {
  authError: string | null;
  authEmail: string;
  authPassword: string;
  isBusy: boolean;
  trustMessage?: string | null;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onLogin: () => void;
};

export function WelcomeScreen({
  authError,
  authEmail,
  authPassword,
  isBusy,
  trustMessage,
  onEmailChange,
  onPasswordChange,
  onLogin,
}: Props): JSX.Element {
  return (
    <main className="sidepanel-auth">
      <section className="auth-card">
        <div className="app-mark">IT</div>
        <h1>IncomeTax Agent</h1>
        <p>Sign in to open your filing chat.</p>
        {trustMessage ? <p className="auth-trust">{trustMessage}</p> : null}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onLogin();
          }}
        >
          <label>
            Email
            <input
              value={authEmail}
              onChange={(event) => onEmailChange(event.target.value)}
              placeholder="you@firm.com"
              type="email"
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              value={authPassword}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder="Password"
              type="password"
              autoComplete="current-password"
              minLength={8}
              required
            />
          </label>
          {authError ? <p className="chat-error">{authError}</p> : null}
          <button className="chat-button primary" type="submit" disabled={isBusy}>
            {isBusy ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
