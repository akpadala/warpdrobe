export const CATEGORIES = ["top", "bottom", "dress", "outerwear", "shoes", "accessory"] as const;
export const COLORS = [
  "black", "white", "grey", "beige", "brown", "red", "orange", "yellow",
  "green", "blue", "navy", "purple", "pink", "metallic", "multi",
] as const;
export const SEASONS = ["spring", "summer", "fall", "winter"] as const;
export const FORMALITY: Record<number, string> = {
  1: "Lounge", 2: "Casual", 3: "Smart casual", 4: "Business", 5: "Formal",
};
export const WARMTH: Record<number, string> = {
  1: "Very light", 2: "Light", 3: "Medium", 4: "Warm", 5: "Very warm",
};

export type Category = (typeof CATEGORIES)[number];
export type Color = (typeof COLORS)[number];

export interface Me {
  id: number;
  email: string;
  name: string;
  has_calendar: boolean;
  location_name: string | null;
  latitude: number | null;
  longitude: number | null;
  is_admin: boolean;
}

export interface Item {
  id: number;
  name: string;
  category: Category;
  color: Color;
  secondary_color: Color | null;
  pattern: string;
  formality: number;
  warmth: number;
  seasons: string[];
  price: number | null;
  purchased_on: string | null;
  tag_source: "gemini" | "fallback" | "user";
  image_url: string | null;
  wear_count: number;
  last_worn: string | null;
  cost_per_wear: number | null;
}

export interface Weather {
  date: string;
  temp_max_c: number;
  temp_min_c: number;
  precip_chance: number;
  summary: string;
}

export interface CalEvent {
  title: string;
  start: string | null;
  all_day: boolean;
  formality: number;
  dress_code: string;
}

export interface Suggestion {
  rank: number;
  score: number;
  parts: Record<string, number>;
  reasons: string[];
  items: Item[];
}

export interface Plan {
  date: string;
  weather: Weather | null;
  events: CalEvent[];
  target_formality: number;
  occasion: string | null;
  warnings: string[];
  suggestions: Suggestion[];
}

export interface Outfit {
  id: number;
  for_date: string;
  item_ids: number[];
  occasion: string | null;
  engine_score: number | null;
  rank: number | null;
  rating: number | null;
  worn: boolean;
}

export interface NextBuy {
  name: string;
  category: Category;
  color: Color;
  formality: number;
  new_outfits: number;
}

export interface Insights {
  totals: {
    items: number;
    closet_value: number;
    wears_logged: number;
    avg_cost_per_wear: number | null;
    outfit_combos: number;
  };
  cost_per_wear: Item[];
  never_worn: Item[];
  resell: { item: Item; why: string }[];
  next_buys: NextBuy[];
  pairing_source: string;
}
