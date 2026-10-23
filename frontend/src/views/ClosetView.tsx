import { useEffect, useRef, useState } from "react";
import { api, post } from "../api";
import { CATEGORIES, type Item } from "../types";
import ItemEditor from "./ItemEditor";
import ItemThumb from "./ItemThumb";

export default function ClosetView() {
  const [items, setItems] = useState<Item[] | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [editing, setEditing] = useState<Item | null>(null);
  const [reviewQueue, setReviewQueue] = useState<Item[]>([]);
  const [uploading, setUploading] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<Item[]>("/api/items").then(setItems).catch((e) => setError(e.message));
  }, []);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setError("");
    const list = Array.from(files);
    const added: Item[] = [];
    setUploading({ done: 0, total: list.length });
    for (const [i, f] of list.entries()) {
      const form = new FormData();
      form.append("photo", f);
      try {
        added.push(await post<Item>("/api/items", form));
      } catch (e) {
        setError(`${f.name}: ${(e as Error).message}`);
      }
      setUploading({ done: i + 1, total: list.length });
    }
    setUploading(null);
    if (fileRef.current) fileRef.current.value = "";
    setItems((prev) => [...added, ...(prev ?? [])]);
    // Review each new item's tags right away; it takes a few seconds and fixes most AI mistakes.
    if (added.length) {
      setEditing(added[0]);
      setReviewQueue(added.slice(1));
    }
  }

  function closeEditor() {
    const [next, ...rest] = reviewQueue;
    setEditing(next ?? null);
    setReviewQueue(rest);
  }

  function saved(item: Item) {
    setItems((prev) => prev?.map((i) => (i.id === item.id ? item : i)) ?? null);
    closeEditor();
  }

  function removed(id: number) {
    setItems((prev) => prev?.filter((i) => i.id !== id) ?? null);
    closeEditor();
  }

  const shown = items?.filter((i) => filter === "all" || i.category === filter) ?? [];

  return (
    <div className="stack">
      <div className="row between">
        <h2>Closet {items && <span className="muted">({items.length})</span>}</h2>
        <label className="primary upload">
          {uploading ? `Tagging ${uploading.done}/${uploading.total}…` : "+ Add photos"}
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            multiple
            disabled={!!uploading}
            onChange={(e) => upload(e.target.files)}
            hidden
          />
        </label>
      </div>
      <p className="muted small">Snap one item per photo on a plain background. Tags are filled in for you; just check them.</p>

      <div className="chips">
        {["all", ...CATEGORIES].map((c) => (
          <button key={c} className={filter === c ? "on" : ""} onClick={() => setFilter(c)}>
            {c === "all" ? "All" : c}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {!items && !error && <div className="skeleton" />}
      {items && items.length === 0 && (
        <div className="card empty">
          <p>Your closet is empty. Start with 5–10 things you wear a lot: a few tops, bottoms, and shoes.</p>
        </div>
      )}

      <div className="grid">
        {shown.map((it) => (
          <div key={it.id} className="grid-cell">
            <ItemThumb item={it} onClick={() => setEditing(it)} />
            <div className="meta">
              {it.wear_count}× worn{it.cost_per_wear !== null && ` · $${it.cost_per_wear.toFixed(2)}/wear`}
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <ItemEditor
          key={editing.id}
          item={editing}
          reviewing={reviewQueue.length > 0 || editing.tag_source !== "user"}
          remaining={reviewQueue.length}
          onSaved={saved}
          onDeleted={removed}
          onClose={closeEditor}
        />
      )}
    </div>
  );
}
