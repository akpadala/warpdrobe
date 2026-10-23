import { useEffect, useState } from "react";
import { api } from "../api";
import { daysAgo, isoDay, money } from "../format";
import { FORMALITY, type Insights } from "../types";
import ItemThumb, { swatch } from "./ItemThumb";

export default function InsightsView() {
  const [data, setData] = useState<Insights | null>(null);
  const [error, setError] = useState("");
  const today = isoDay(new Date());

  useEffect(() => {
    api<Insights>("/api/insights").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <div className="skeleton" />;
  const t = data.totals;

  return (
    <div className="stack">
      <div className="stats">
        <div className="stat">
          <b>{t.items}</b>
          <span>items</span>
        </div>
        <div className="stat">
          <b>{t.outfit_combos}</b>
          <span>outfit combos</span>
        </div>
        <div className="stat">
          <b>{money(t.avg_cost_per_wear)}</b>
          <span>avg cost / wear</span>
        </div>
      </div>

      <section className="section">
        <header>
          <span className="eyebrow">Gap finder</span>
          <h3>Best next buy</h3>
          <p className="muted small">The one piece that would unlock the most new outfits with what you already own.</p>
        </header>
        {data.next_buys.length === 0 && <p className="muted">Add a few more items first.</p>}
        {data.next_buys.map((b) => (
          <div key={b.name} className="buy">
            <span className="dot" style={{ background: swatch(b.color) }} />
            <span className="grow">
              <b className="cap">
                {b.color} {b.category}
              </b>
              <span className="muted small"> · {FORMALITY[b.formality]}</span>
            </span>
            <span className="pill f3 count">+{b.new_outfits} outfits</span>
          </div>
        ))}
      </section>

      <section className="section">
        <header>
          <span className="eyebrow">Closet cleanout</span>
          <h3>Resell or donate?</h3>
        </header>
        {data.resell.length === 0 ? (
          <p className="muted">Nothing gathering dust. Nice.</p>
        ) : (
          <div className="list">
            {data.resell.map(({ item, why }) => (
              <div key={item.id} className="list-row">
                <ItemThumb item={item} />
                <span className="muted small">{why}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <header>
          <span className="eyebrow">Value</span>
          <h3>Cost per wear</h3>
          <p className="muted small">Price ÷ times worn. Add prices in the closet to see this.</p>
        </header>
        <table className="cpw">
          <thead>
            <tr>
              <th>Item</th>
              <th>Paid</th>
              <th>Worn</th>
              <th>Per wear</th>
            </tr>
          </thead>
          <tbody>
            {data.cost_per_wear.map((i) => (
              <tr key={i.id}>
                <td>
                  {i.name}
                  <div className="muted small">last {daysAgo(i.last_worn, today)}</div>
                </td>
                <td>{money(i.price)}</td>
                <td>{i.wear_count}×</td>
                <td>
                  <b>{money(i.cost_per_wear)}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <p className="muted small center">
        Pairing scores: {data.pairing_source === "hm" ? "learned from H&M purchase data" : "color rules"}
      </p>
    </div>
  );
}
