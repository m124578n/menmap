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

/** 面板會遮住地圖的一部分:算出「看得到的區域」padding,fitBounds / easeTo 用。 */
function visiblePadding(mode: "list" | "detail"): { top: number; bottom: number; left: number; right: number } {
  const mobile = window.innerWidth < 768;
  if (mobile) {
    // 上方 topbar + chips 約 110px;下方 bottom sheet 45vh、詳情面板 66vh(見 app.css)
    const sheet = mode === "detail" ? 0.66 : 0.45;
    return { top: 110, bottom: Math.round(window.innerHeight * sheet) + 12, left: 16, right: 16 };
  }
  // 桌機:左側 380px 抽屜 + 12px 邊距
  return { top: 110, bottom: 24, left: 380 + 24, right: 24 };
}

// 聚合泡泡:深色底圖上要用亮一點的靛藍,否則和底圖糊在一起
const CLUSTER = {
  light: { fill: "#22405f", text: "#ffffff", stroke: "rgba(255,255,255,0.6)" },
  dark: { fill: "#6e93c9", text: "#15130f", stroke: "rgba(21,19,15,0.6)" },
};

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

function addLayers(map: maplibregl.Map, data: GeoJSON.FeatureCollection,
                   theme: "light" | "dark") {
  if (map.getSource(SRC)) return;
  const cl = CLUSTER[theme];
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
      "circle-color": cl.fill,
      "circle-opacity": 0.92,
      "circle-radius": ["step", ["get", "point_count"], 16, 10, 20, 30, 26],
      "circle-stroke-width": 2,
      "circle-stroke-color": cl.stroke,
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
    paint: { "text-color": cl.text },
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
  const themeRef = useRef(theme);
  onSelectRef.current = onSelect;
  onBoundsRef.current = onBoundsChange;
  themeRef.current = theme;

  // 初始化(一次)
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE[theme],
      bounds: TW_BOUNDS,
      fitBoundsOptions: { padding: visiblePadding("list") },
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.GeolocateControl({ trackUserLocation: false }), "bottom-right");

    const emitBounds = () => onBoundsRef.current(map.getBounds());

    map.on("load", () => {
      addLayers(map, dataRef.current, themeRef.current);
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
      addLayers(map, dataRef.current, theme);
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
      // padding 讓店家落在「沒被面板遮住」的區域中央
      if (s)
        map.easeTo({
          center: [s.lng, s.lat],
          zoom: Math.max(map.getZoom(), 15),
          padding: visiblePadding("detail"),
          duration: 500,
        });
    }
  }, [selected, shops]);

  return <div className="map" ref={containerRef} />;
}

function applySelected(map: maplibregl.Map, selected: string | null) {
  if (!map.getLayer("selected")) return;
  map.setFilter("selected", ["==", ["get", "ftid"], selected ?? "__none__"]);
}
