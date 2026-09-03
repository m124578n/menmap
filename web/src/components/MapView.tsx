import { useEffect, useRef } from "react";
import maplibregl, { type LngLatBoundsLike } from "maplibre-gl";
import type { Shop } from "../types";
import { STATUS_COLOR } from "../lib/format";

const STYLE = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};

// 雙北大致範圍
const TW_BOUNDS: LngLatBoundsLike = [
  [121.28, 24.88],
  [121.75, 25.22],
];

const SRC = "shops";

interface Props {
  shops: Shop[];
  selected: string | null;
  theme: "light" | "dark";
  onSelect: (ftid: string) => void;
  onBoundsChange: (bounds: maplibregl.LngLatBounds) => void;
}

function toGeoJSON(shops: Shop[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: shops.map((s) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [s.lng, s.lat] },
      properties: {
        ftid: s.ftid,
        name: s.name ?? "",
        status: s.status ?? "UNKNOWN",
      },
    })),
  };
}

function addLayers(map: maplibregl.Map, data: GeoJSON.FeatureCollection) {
  if (map.getSource(SRC)) return;
  map.addSource(SRC, {
    type: "geojson",
    data,
    cluster: true,
    clusterRadius: 48,
    clusterMaxZoom: 14,
  });

  // 聚合泡泡(藍染靛)
  map.addLayer({
    id: "clusters",
    type: "circle",
    source: SRC,
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#22405f",
      "circle-opacity": 0.92,
      "circle-radius": ["step", ["get", "point_count"], 16, 10, 20, 30, 26],
      "circle-stroke-width": 2,
      "circle-stroke-color": "rgba(255,255,255,0.6)",
    },
  });
  map.addLayer({
    id: "cluster-count",
    type: "symbol",
    source: SRC,
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["get", "point_count_abbreviated"],
      "text-font": ["Open Sans Bold", "Noto Sans Bold"],
      "text-size": 12,
    },
    paint: { "text-color": "#ffffff" },
  });

  // 單點:依狀態上色
  map.addLayer({
    id: "points",
    type: "circle",
    source: SRC,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "match",
        ["get", "status"],
        "OPERATIONAL", STATUS_COLOR.OPERATIONAL,
        "CLOSED_TEMPORARILY", STATUS_COLOR.CLOSED_TEMPORARILY,
        "CLOSED_PERMANENTLY", STATUS_COLOR.CLOSED_PERMANENTLY,
        STATUS_COLOR.UNKNOWN,
      ],
      "circle-radius": 7,
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff",
    },
  });

  // 選中:朱紅環
  map.addLayer({
    id: "selected",
    type: "circle",
    source: SRC,
    filter: ["==", ["get", "ftid"], "__none__"],
    paint: {
      "circle-radius": 11,
      "circle-color": "rgba(0,0,0,0)",
      "circle-stroke-width": 3,
      "circle-stroke-color": "#c1352b",
    },
  });
}

export default function MapView({
  shops,
  selected,
  theme,
  onSelect,
  onBoundsChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const dataRef = useRef<GeoJSON.FeatureCollection>(toGeoJSON(shops));
  const onSelectRef = useRef(onSelect);
  const onBoundsRef = useRef(onBoundsChange);
  onSelectRef.current = onSelect;
  onBoundsRef.current = onBoundsChange;

  // 初始化(一次)
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE[theme],
      bounds: TW_BOUNDS,
      fitBoundsOptions: { padding: 40 },
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.GeolocateControl({ trackUserLocation: false }), "bottom-right");

    const emitBounds = () => onBoundsRef.current(map.getBounds());

    map.on("load", () => {
      addLayers(map, dataRef.current);
      emitBounds();
    });
    map.on("moveend", emitBounds);

    // 點聚合 → 展開放大
    map.on("click", "clusters", (e) => {
      const f = map.queryRenderedFeatures(e.point, { layers: ["clusters"] })[0];
      const clusterId = f.properties?.cluster_id;
      const src = map.getSource(SRC) as maplibregl.GeoJSONSource;
      src.getClusterExpansionZoom(clusterId).then((zoom) => {
        map.easeTo({ center: (f.geometry as GeoJSON.Point).coordinates as [number, number], zoom });
      });
    });
    // 點單店 → 選取
    map.on("click", "points", (e) => {
      const ftid = e.features?.[0]?.properties?.ftid;
      if (ftid) onSelectRef.current(String(ftid));
    });
    for (const layer of ["clusters", "points"]) {
      map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 資料更新
  useEffect(() => {
    dataRef.current = toGeoJSON(shops);
    const map = mapRef.current;
    const src = map?.getSource(SRC) as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(dataRef.current);
  }, [shops]);

  // 主題切換:換底圖並重建圖層
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setStyle(STYLE[theme]);
    const onStyle = () => {
      addLayers(map, dataRef.current);
      applySelected(map, selected);
    };
    map.once("styledata", onStyle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  // 選中高亮 + 飛過去
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    applySelected(map, selected);
    if (selected) {
      const s = shops.find((x) => x.ftid === selected);
      if (s) map.easeTo({ center: [s.lng, s.lat], zoom: Math.max(map.getZoom(), 15), duration: 500 });
    }
  }, [selected, shops]);

  return <div className="map" ref={containerRef} />;
}

function applySelected(map: maplibregl.Map, selected: string | null) {
  if (!map.getLayer("selected")) return;
  map.setFilter("selected", ["==", ["get", "ftid"], selected ?? "__none__"]);
}
