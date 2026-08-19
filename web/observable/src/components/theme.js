// GÉNÉRÉ par web/export/theme.py — NE PAS ÉDITER À LA MAIN.
// Source de vérité : web/theme.json  ·  régénérer : python web/export/web_export.py
export const THEME = {
  "brand": {
    "bg": "#FFFFFF",
    "surface": "#F5F5F5",
    "ink": "#2D3748",
    "brick": "#E64A19",
    "terracotta": "#D0A37D",
    "sunflower": "#FBC02D",
    "blue": "#64B5F6",
    "green": "#388E3C"
  },
  "series": {
    "brick": "#E64A19",
    "blue": "#1F78B4",
    "green": "#388E3C",
    "violet": "#6A4C93",
    "gold": "#B07D10"
  },
  "status": {
    "up": {
      "fg": "#2E7D32",
      "bg": "rgba(56,142,60,0.12)"
    },
    "flat": {
      "fg": "#7A5D00",
      "bg": "rgba(251,192,45,0.20)"
    },
    "down": {
      "fg": "#B23A12",
      "bg": "rgba(230,74,25,0.12)"
    },
    "unknown": {
      "fg": "#555555",
      "bg": "#ECECEC"
    }
  },
  "delta": {
    "positive": "#2E7D32",
    "negative": "#C0392B",
    "neutral": "#7A7A7A"
  },
  "ui": {
    "link": "#1E88E5",
    "subtle": "#6c757d",
    "muted": "#4A5568",
    "rule": "#B0B7C3",
    "greyLine": "#9AA5B1",
    "border": "#E7E9ED",
    "borderLight": "#EDEFF2"
  },
  "font": {
    "sans": "\"Source Sans 3\", \"Segoe UI\", Tahoma, Geneva, Verdana, sans-serif",
    "heading": "\"Segoe UI\", Tahoma, Geneva, Verdana, sans-serif"
  }
};

export const {brand, series, status, delta, ui} = THEME;

// Rampe catégorielle dans son ordre d'assignation (jamais cyclée).
export const SERIES_ORDER = [series.brick, series.blue, series.green, series.violet, series.gold];
