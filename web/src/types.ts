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
  cover: string | null;
  maps_url: string | null;
}

export interface ShopsData {
  generated_at: string | null;
  shops: Shop[];
}
