export type BusinessStatus =
  | "OPERATIONAL"
  | "CLOSED_TEMPORARILY"
  | "CLOSED_PERMANENTLY"
  | null;

export interface Shop {
  ftid: string;
  name: string | null;
  lat: number;
  lng: number;
  city: string | null;
  district: string | null;
  types: string[];
  status: BusinessStatus;
  rating: number | null;
  rating_count: number | null;
  price: string | null;
  hours: [string, string[]][] | null;  // [[星期名, ["11:00–21:30", ...]], ...]
  added_at: string | null;
  is_new: boolean;
  cover: string | null;
  maps_url: string | null;
}

export interface ShopsData {
  generated_at: string | null;
  shops: Shop[];
}

/** discover.json:麵榜與本週動態(scripts/export_web_data.py 每天產) */
export interface DiscoverData {
  generated_at: string;
  window: { from: string; to: string; days: number };
  hot: { ftid: string; score: number }[];
  rising: { ftid: string; delta: number; days: number }[];
  starter: { ftid: string }[];
  weekly: {
    new_shops: { ftid: string; added_at: string }[];
    status_changes: { ftid: string; from: BusinessStatus; to: BusinessStatus; at: string }[];
    rating_jumps: { ftid: string; from: number; to: number }[];
    hours_changes: { ftid: string }[];
    renames: { ftid: string; field: "name" | "address"; old: string; new: string }[];
  };
}
