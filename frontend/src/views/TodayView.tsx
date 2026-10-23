import { useEffect, useMemo, useState } from "react";
import { api, patch, post } from "../api";
import { dayLabel, isoDay, nextDays, timeLabel, toF } from "../format";
import { FORMALITY, type Me, type Outfit, type Plan, type Suggestion } from "../types";
import ItemThumb from "./ItemThumb";

interface Props {
  me: Me;
  onGoSettings: () => void;
  onGoCloset: () => void;
}

type Saved = Record<number, Outfit>; // by suggestion rank

export default function TodayView({ me, onGoSettings, onGoCloset }: Props) {
  const today = isoDay(new Date());
  const days = useMemo(() => nextDays(new Date(), 7), []);
  const [day, setDay] = useState(today);
  const [override, setOverride] = useState<number | "">("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Saved>({});

  useEffect(() => {
    let live = true;
    setPlan(null);
    setError("");
    setSaved({});
    const q = new URLSearchParams({ day });
    if (override !== "") q.set("formality", String(override));
    api<Plan>(`/api/plan?${q}`)
      .then((p) => live && setPlan(p))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [day, override]);

  async function record(s: Suggestion, change: { rating?: number; worn?: boolean }) {
    const existing = saved[s.rank];
    try {
      const outfit = existing
        ? await patch<Outfit>(`/api/outfits/${existing.id}`, change)
        : await post<Outfit>("/api/outfits", {
            for_date: day,
            item_ids: s.items.map((i) => i.id),
            occasion: plan?.occasion ?? null,
            engine_score: s.score,
            rank: s.rank,
            ...change,
          });
      setSaved((prev) => ({ ...prev, [s.rank]: outfit }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const needsSetup = !me.has_calendar || me.latitude === null;

  return (
    <div className="stack">
      <div className="daystrip" role="tablist" aria-label="Day">
        {days.map((d) => (
          <button key={d} className={d === day ? "on" : ""} onClick={() => setDay(d)} role="tab" aria-selected={d === day}>
            <span>{dayLabel(d, today)}</span>
            <b>{Number(d.slice(8))}</b>
          </button>
        ))}
      </div>

      {needsSetup && (
        <button className="banner" onClick={onGoSettings}>
          {me.latitude === null ? "Add your city" : "Connect your calendar"} so outfits match your day →
        </button>
      )}

      {error && <p className="error">{error}</p>}
      {!plan && !error && <div className="skeleton" />}

      {plan && (
        <>
          <section className="context">
            {plan.weather ? (
              <div className="wx">
                <div className="temp">{toF(plan.weather.temp_max_c)}°</div>
                <div>
                  <div className="cap">{plan.weather.summary}</div>
                  <div className="muted">
                    Low {toF(plan.weather.temp_min_c)}° · {plan.weather.precip_chance}% rain
                  </div>
                </div>
              </div>
            ) : (
              <div className="muted">No weather for this day.</div>
            )}
            <div className="events">
              {plan.events.length === 0 && <div className="muted">Nothing on the calendar.</div>}
              {plan.events.map((e, i) => (
                <div key={i} className="event">
                  <span className="time">{timeLabel(e.start)}</span>
                  <span className="title">{e.title}</span>
                  <span className={`pill f${e.formality}`}>{e.dress_code}</span>
                </div>
              ))}
            </div>
            <label className="inline">
              Dress code
              <select value={override} onChange={(e) => setOverride(e.target.value === "" ? "" : Number(e.target.value))}>
                <option value="">Auto ({FORMALITY[plan.target_formality]})</option>
                {[1, 2, 3, 4, 5].map((f) => (
                  <option key={f} value={f}>
                    {FORMALITY[f]}
                  </option>
                ))}
              </select>
            </label>
          </section>

          {plan.warnings
            .filter((w) => !w.includes("Settings"))
            .map((w) => (
              <p key={w} className="note">
                {w}
              </p>
            ))}

          {plan.suggestions.length === 0 && (
            <div className="empty">
              <p>Add at least one top and one bottom (or a dress) and your outfits show up here.</p>
              <button className="primary" onClick={onGoCloset}>
                Add clothes
              </button>
            </div>
          )}

          {plan.suggestions.map((s) => {
            const o = saved[s.rank];
            return (
              <article key={s.rank} className="outfit">
                <header>
                  <h3>{s.rank === 1 ? "Top pick" : `Option ${s.rank}`}</h3>
                  <span className="score" title="Match score">
                    {Math.round(s.score * 100)}%
                  </span>
                </header>
                <div className="outfit-items">
                  {s.items.map((it) => (
                    <ItemThumb key={it.id} item={it} />
                  ))}
                </div>
                <ul className="reasons">
                  {s.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
                <footer>
                  <div className="stars" aria-label="Rate this outfit">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        className={o?.rating && n <= o.rating ? "lit" : ""}
                        onClick={() => record(s, { rating: n })}
                        aria-label={`${n} star${n > 1 ? "s" : ""}`}
                      >
                        ★
                      </button>
                    ))}
                  </div>
                  <button className={o?.worn ? "done" : "primary"} disabled={o?.worn} onClick={() => record(s, { worn: true })}>
                    {o?.worn ? "Logged ✓" : day === today ? "Wearing this" : "Plan this"}
                  </button>
                </footer>
              </article>
            );
          })}
        </>
      )}
    </div>
  );
}
