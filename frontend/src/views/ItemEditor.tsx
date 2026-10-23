import { useState, type FormEvent } from "react";
import { del, patch, post } from "../api";
import { isoDay } from "../format";
import { CATEGORIES, COLORS, FORMALITY, SEASONS, WARMTH, type Item } from "../types";
import { swatch } from "./ItemThumb";

interface Props {
  item: Item;
  reviewing: boolean;
  remaining: number;
  onSaved: (item: Item) => void;
  onDeleted: (id: number) => void;
  onClose: () => void;
}

export default function ItemEditor({ item, reviewing, remaining, onSaved, onDeleted, onClose }: Props) {
  const [form, setForm] = useState({
    name: item.name,
    category: item.category,
    color: item.color,
    formality: item.formality,
    warmth: item.warmth,
    seasons: item.seasons,
    price: item.price === null ? "" : String(item.price),
    purchased_on: item.purchased_on ?? "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const updated = await patch<Item>(`/api/items/${item.id}`, {
        ...form,
        price: form.price === "" ? null : Number(form.price),
        purchased_on: form.purchased_on || null,
      });
      onSaved(updated);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm(`Delete “${item.name}”?`)) return;
    await del(`/api/items/${item.id}`);
    onDeleted(item.id);
  }

  async function woreToday() {
    const updated = await post<Item>(`/api/items/${item.id}/wear?on=${isoDay(new Date())}`);
    onSaved(updated);
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <form className="sheet" onClick={(e) => e.stopPropagation()} onSubmit={save}>
        <header className="row between">
          <h3>{reviewing ? "Check the tags" : "Edit item"}</h3>
          <button type="button" className="ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        {item.image_url && <img className="sheet-img" src={item.image_url} alt="" />}
        {item.tag_source === "fallback" && (
          <p className="note">Auto-tagging is offline, so only the color was detected. Please pick the type.</p>
        )}
        <label>
          Name
          <input value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={120} required />
        </label>
        <fieldset>
          <legend>Type</legend>
          <div className="chips">
            {CATEGORIES.map((c) => (
              <button type="button" key={c} className={form.category === c ? "on" : ""} onClick={() => set("category", c)}>
                {c}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Color</legend>
          <div className="swatches">
            {COLORS.map((c) => (
              <button
                type="button"
                key={c}
                title={c}
                aria-label={c}
                className={form.color === c ? "on" : ""}
                style={{ background: swatch(c) }}
                onClick={() => set("color", c)}
              />
            ))}
          </div>
        </fieldset>
        <label>
          <span>
            Dressiness: <b>{FORMALITY[form.formality]}</b>
          </span>
          <input type="range" min={1} max={5} value={form.formality} onChange={(e) => set("formality", Number(e.target.value))} />
        </label>
        <label>
          <span>
            Warmth: <b>{WARMTH[form.warmth]}</b>
          </span>
          <input type="range" min={1} max={5} value={form.warmth} onChange={(e) => set("warmth", Number(e.target.value))} />
        </label>
        <fieldset>
          <legend>Seasons</legend>
          <div className="chips">
            {SEASONS.map((s) => (
              <button
                type="button"
                key={s}
                className={form.seasons.includes(s) ? "on" : ""}
                onClick={() => set("seasons", form.seasons.includes(s) ? form.seasons.filter((x) => x !== s) : [...form.seasons, s])}
              >
                {s}
              </button>
            ))}
          </div>
        </fieldset>
        <div className="row two">
          <label>
            Price paid ($)
            <input type="number" inputMode="decimal" min={0} step="0.01" value={form.price} onChange={(e) => set("price", e.target.value)} />
          </label>
          <label>
            Bought on
            <input type="date" value={form.purchased_on} onChange={(e) => set("purchased_on", e.target.value)} />
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="row between">
          <button type="button" className="ghost danger" onClick={remove}>
            Delete
          </button>
          {!reviewing && (
            <button type="button" className="ghost" onClick={woreToday}>
              Wore it today
            </button>
          )}
          <button className="primary" disabled={busy}>
            {reviewing ? (remaining ? `Looks good · ${remaining} more` : "Looks good") : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
