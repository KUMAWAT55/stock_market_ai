import { FormEvent, useState } from "react";

import { submitContact } from "../api";

export default function ContactPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("");
    setBusy(true);
    try {
      await submitContact({
        full_name: fullName,
        email,
        subject,
        message,
      });
      setStatus("Message submitted. Our team will contact you.");
      setFullName("");
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to submit message");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="content-card">
        <h1>Contact Us</h1>
        <p>For product demos, integrations, and trading desk onboarding, send your message below.</p>
        <form className="auth-form" onSubmit={onSubmit}>
          <label>
            Full Name
            <input value={fullName} onChange={(event) => setFullName(event.target.value)} required />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Subject
            <input value={subject} onChange={(event) => setSubject(event.target.value)} required />
          </label>
          <label>
            Message
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={6}
              required
            />
          </label>
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "Sending..." : "Submit"}
          </button>
        </form>
        {status && <p className="form-status">{status}</p>}
      </section>
    </main>
  );
}
