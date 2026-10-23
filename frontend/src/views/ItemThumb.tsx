import { COLORS, type Item } from "../types";

/** Garment colors come from the --swatch-* theme variables in styles.css. */
export function swatch(color: string): string {
  return (COLORS as readonly string[]).includes(color) ? `var(--swatch-${color})` : "var(--swatch-grey)";
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
