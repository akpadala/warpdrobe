import type { Item } from "../types";

const SWATCH: Record<string, string> = {
  black: "#1f1f1f", white: "#f4f4f4", grey: "#9a9a9a", beige: "#d8c6a3", brown: "#7a5232",
  red: "#c62f3b", orange: "#e8812f", yellow: "#efd04a", green: "#4c8a50", blue: "#4d7fd0",
  navy: "#243056", purple: "#7d4fa0", pink: "#eb9ab8", metallic: "#c0b283",
  multi: "conic-gradient(#c62f3b, #efd04a, #4c8a50, #4d7fd0, #7d4fa0, #c62f3b)",
};

export function swatch(color: string): string {
  return SWATCH[color] ?? "#999";
}

export default function ItemThumb({ item, onClick }: { item: Item; onClick?: () => void }) {
  const body = (
    <>
      {item.image_url ? (
        <img src={item.image_url} alt={item.name} loading="lazy" />
      ) : (
        <div className="noimg" style={{ background: swatch(item.color) }} />
      )}
      <span className="thumb-name">{item.name}</span>
    </>
  );
  return onClick ? (
    <button className="thumb" onClick={onClick}>
      {body}
    </button>
  ) : (
    <div className="thumb">{body}</div>
  );
}
