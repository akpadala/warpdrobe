import { useEffect, useState, type FormEvent } from "react";
import { api, patch, post } from "../api";
import type { Me } from "../types";

interface Props {
  me: Me;
  onChange: (me: Me) => void;
  onSignOut: () => void;
}

export default function SettingsView({ me, onChange, onSignOut }: Props) {
  const [city, setCity] = useState("");
  const [ics, setIcs] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (me.is_admin) api<Record<string, unknown>>("/api/admin/metrics").then(setMetrics).catch(() => {});
  }, [me.is_admin]);

  async function update(body: object, success: string) {
    setBusy(true);
    setMsg(null);
    try {
      onChange(await patch<Me>("/api/me", body));
      setMsg({ ok: true, text: success });
      return true;
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
      return false;
    } finally {
      setBusy(false);
    }
  }

  function useMyLocation() {
    if (!navigator.geolocation) return setMsg({ ok: false, text: "Location isn't available in this browser." });
    navigator.geolocation.getCurrentPosition(
      (pos) => update({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }, "Location saved."),
      () => setMsg({ ok: false, text: "Location permission was denied. Type your city instead." }),
    );
  }

  return (
    <div className="stack">
      <h2>Settings</h2>
      {msg && <p className={msg.ok ? "success" : "error"}>{msg.text}</p>}

      <section className="card">
        <h3>Weather location</h3>
        <p className="muted small">{me.location_name ? `Using ${me.location_name}.` : "Not set yet."}</p>
        <form
          className="row"
          onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            if (await update({ location_query: city }, "Location saved.")) setCity("");
          }}
        >
          <input placeholder="City, e.g. Chapel Hill" value={city} onChange={(e) => setCity(e.target.value)} required />
          <button className="primary" disabled={busy}>
            Save
          </button>
        </form>
        <button className="ghost" onClick={useMyLocation} disabled={busy}>
          Use my current location
        </button>
      </section>

      <section className="card">
        <h3>Google Calendar</h3>
        <p className="muted small">
          {me.has_calendar ? "Connected. Outfits follow your events." : "Not connected."} Only event titles and times are read.
        </p>
        <details>
          <summary>How to get your private calendar link</summary>
          <ol className="small">
            <li>
              On a computer, open <b>calendar.google.com</b> → gear icon → <b>Settings</b>.
            </li>
            <li>Under “Settings for my calendars”, click your calendar.</li>
            <li>
              Scroll to <b>Integrate calendar</b> and copy <b>Secret address in iCal format</b>.
            </li>
            <li>Paste it below. Treat it like a password.</li>
          </ol>
        </details>
        <form
          className="row"
          onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            if (await update({ ics_url: ics }, "Calendar connected.")) setIcs("");
          }}
        >
          <input placeholder="https://calendar.google.com/calendar/ical/…" value={ics} onChange={(e) => setIcs(e.target.value)} required />
          <button className="primary" disabled={busy}>
            Connect
          </button>
        </form>
        {me.has_calendar && (
          <button className="ghost danger" onClick={() => update({ ics_url: "" }, "Calendar disconnected.")} disabled={busy}>
            Disconnect calendar
          </button>
        )}
      </section>

      {metrics && (
        <section className="card">
          <h3>Usage (admin)</h3>
          <pre className="metrics">{JSON.stringify(metrics, null, 2)}</pre>
        </section>
      )}

      <section className="card row between">
        <span className="muted small">Signed in as {me.email}</span>
        <button
          className="ghost"
          onClick={async () => {
            await post("/api/auth/logout").catch(() => {});
            onSignOut();
          }}
        >
          Sign out
        </button>
      </section>
    </div>
  );
}
