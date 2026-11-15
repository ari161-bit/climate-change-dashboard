"""Report builder: the same report content exported as CSV or PDF.

The PDF writer is a small, dependency-free implementation of the PDF 1.4
format (Helvetica text, tables, coloured rules), so no extra package is needed.
"""
import csv
import io
from datetime import datetime

from . import datasources, ml

REPORTS = {
    "summary": "Climate summary",
    "temperature": "Temperature analysis",
    "rainfall": "Rainfall analysis",
    "anomalies": "Anomaly report",
    "predictions": "Prediction results",
    "regional": "Regional comparison",
}


def build(kind, params=None):
    """Return {'title', 'subtitle', 'sections': [{'heading', 'note', 'columns', 'rows'}]}."""
    params = params or {}
    country = params.get("country") or "World"
    sections = []

    if kind in ("summary", "temperature", "predictions"):
        tt = ml.temperature_trend(country)
        if tt:
            if kind in ("summary", "temperature"):
                rows = [[y, f"{a:+.2f}", f"{f:+.2f}"] for y, a, f in zip(tt["years"], tt["actual"], tt["fitted"])]
                sections.append({"heading": f"Temperature change vs 1951-1980: {country}",
                                 "note": f"Source: {tt['source']}. Warming rate {tt['warming_per_decade']:+.3f} °C per decade.",
                                 "columns": ["Year", "Observed (°C)", "Model fit (°C)"],
                                 "rows": rows if kind == "temperature" else rows[-10:]})
            sections.append({"heading": "Model evaluation (hold-out: last 10 years)",
                             "note": f"Best model: {tt['best_model']}. Metrics measured on years the model never saw.",
                             "columns": ["Model", "MAE", "RMSE", "R²"],
                             "rows": [[e["model"], e["MAE"], e["RMSE"], e["R2"]] for e in tt["evaluation"]]})
            if kind in ("summary", "predictions"):
                sections.append({"heading": "Forecast",
                                 "note": f"95% band ±{tt['forecast_band']} °C (from model residuals).",
                                 "columns": ["Year", "Predicted anomaly (°C)"],
                                 "rows": [[y, f"{v:+.2f}"] for y, v in zip(tt["future_years"], tt["forecast"])]})

    if kind in ("summary", "rainfall", "predictions"):
        rf = ml.rainfall_model()
        if rf.get("ready"):
            m, b = rf["metrics"], rf["baseline_metrics"]
            sections.append({"heading": "Rainfall prediction model",
                             "note": f"{rf['algorithm']} on station readings ({rf['data_label']}). "
                                     f"{rf['n_train']} train / {rf['n_test']} test readings.",
                             "columns": ["Model", "MAE (mm)", "RMSE (mm)", "R²"],
                             "rows": [["Random forest", m["MAE"], m["RMSE"], m["R2"]],
                                      ["Seasonal baseline", b["MAE"], b["RMSE"], b["R2"]]]})
        if kind == "rainfall":
            df = datasources.readings_frame().dropna(subset=["rainfall"])
            if not df.empty:
                g = df.groupby("station").agg(region=("region", "first"), readings=("rainfall", "size"),
                                              mean_mm=("rainfall", "mean"), max_mm=("rainfall", "max"))
                sections.append({"heading": "Rainfall by station",
                                 "note": f"Data: {datasources.data_badge(set(df['source']))}.",
                                 "columns": ["Station", "Region", "Readings", "Mean (mm)", "Max (mm)"],
                                 "rows": [[s, r["region"], int(r["readings"]), round(float(r["mean_mm"]), 1),
                                           round(float(r["max_mm"]), 1)] for s, r in g.iterrows()]})

    if kind in ("summary", "anomalies"):
        an = ml.anomaly_detection()
        rows = [[a["location"], a.get("date", a["year"]), a["value"], a["score"], a["source"]] for a in an["anomalies"]]
        sections.append({"heading": "Detected anomalies", "note": an["method"],
                         "columns": ["Location", "When", "Value", "Score", "Data"],
                         "rows": rows if kind == "anomalies" else rows[:10]})
        if kind == "anomalies":
            corr = ml.correlation_analysis()
            sections.append({"heading": "Correlations", "note": "Pearson correlation coefficients.",
                             "columns": ["Variable A", "Variable B", "r", "p-value", "n", "Data"],
                             "rows": [[p["a"], p["b"], p["r"], p["p_value"] if p["p_value"] is not None else "-",
                                       p["n"], p["source"]] for p in corr["pairs"]]})

    if kind in ("summary", "regional"):
        pat = ml.patterns()
        sections.append({"heading": "Regional comparison: average temperature change by decade (°C)",
                         "note": f"Source: {pat['source']}.",
                         "columns": ["Region"] + [f"{d}s" for d in pat["decades"]] + ["°C/decade"],
                         "rows": [[r["region"]] + ["-" if v is None else f"{v:+.2f}" for v in r["values"]] +
                                  [f"{r['per_decade']:+.3f}"] for r in pat["rows"]]})

    return {"title": f"EarthScape: {REPORTS.get(kind, 'Report')}",
            "subtitle": f"Generated {datetime.now():%d %b %Y %H:%M} · scope: {country}",
            "sections": sections}


def to_csv(report):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([report["title"]])
    w.writerow([report["subtitle"]])
    for s in report["sections"]:
        w.writerow([])
        w.writerow([s["heading"]])
        if s.get("note"):
            w.writerow([s["note"]])
        w.writerow(s["columns"])
        w.writerows(s["rows"])
    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Minimal PDF writer
# ---------------------------------------------------------------------------
def _pdf_text(s):
    s = str(s).replace("−", "-").replace("²", "2").replace("₂", "2").replace("·", "-").replace("°", " deg")
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class _PDF:
    W, H, M = 595, 842, 50   # A4 in points

    def __init__(self):
        self.pages, self.ops, self.y = [], [], self.H - self.M

    def _new_page(self):
        if self.ops:
            self.pages.append("\n".join(self.ops))
        self.ops, self.y = [], self.H - self.M

    def _need(self, h):
        if self.y - h < self.M:
            self._new_page()

    def text(self, s, size=10, bold=False, color=(0.1, 0.2, 0.15), x=None, gap=4):
        self._need(size + gap)
        self.y -= size
        font = "F2" if bold else "F1"
        r, g, b = color
        self.ops.append(f"{r} {g} {b} rg BT /{font} {size} Tf {x or self.M} {self.y:.1f} Td ({_pdf_text(s)}) Tj ET")
        self.y -= gap

    def wrap(self, s, size=9, width_chars=105, **kw):
        words, line = str(s).split(), ""
        for w in words:
            if len(line) + len(w) + 1 > width_chars:
                self.text(line, size, **kw)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            self.text(line, size, **kw)

    def rule(self, color=(0.09, 0.64, 0.29), width=1.5):
        self._need(8)
        r, g, b = color
        self.ops.append(f"{r} {g} {b} RG {width} w {self.M} {self.y:.1f} m {self.W - self.M} {self.y:.1f} l S")
        self.y -= 8

    def table(self, columns, rows, size=8):
        usable = self.W - 2 * self.M
        widths = [usable / len(columns)] * len(columns)
        if len(columns) > 2:
            widths = [usable * 0.28] + [usable * 0.72 / (len(columns) - 1)] * (len(columns) - 1)

        def line(vals, bold=False, shade=False):
            self._need(size + 6)
            if shade:
                self.ops.append(f"0.94 0.99 0.96 rg {self.M} {self.y - size - 3:.1f} {usable} {size + 6} re f")
            self.y -= size
            x = self.M + 3
            for v, w in zip(vals, widths):
                max_chars = int(w / (size * 0.5))
                t = str(v)
                t = t if len(t) <= max_chars else t[:max_chars - 1] + "~"
                self.ops.append(f"0.1 0.2 0.15 rg BT /{'F2' if bold else 'F1'} {size} Tf {x:.1f} {self.y:.1f} Td ({_pdf_text(t)}) Tj ET")
                x += w
            self.y -= 6

        line(columns, bold=True, shade=True)
        for i, r in enumerate(rows):
            line(r, shade=(i % 2 == 1))

    def output(self):
        self._new_page()
        objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
                "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
        kids = []
        for i, content in enumerate(self.pages):
            footer = f"0.4 0.5 0.45 rg BT /F1 8 Tf {self.M} 25 Td (EarthScape Climate Agency - page {i + 1} of {len(self.pages)}) Tj ET"
            stream = (content + "\n" + footer).encode("latin-1")
            objs.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")
            content_id = len(objs)
            objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.W} {self.H}] "
                        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>")
            kids.append(len(objs))
        objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"

        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, o in enumerate(objs, 1):
            offsets.append(out.tell())
            body = o if isinstance(o, bytes) else o.encode("latin-1")
            out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
        xref = out.tell()
        out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
        for off in offsets:
            out.write(f"{off:010d} 00000 n \n".encode())
        out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
        return out.getvalue()


def to_pdf(report):
    pdf = _PDF()
    pdf.text(report["title"], 18, bold=True, color=(0.04, 0.24, 0.18), gap=6)
    pdf.text(report["subtitle"], 9, color=(0.35, 0.45, 0.4))
    pdf.rule()
    for s in report["sections"]:
        pdf.y -= 6
        pdf.text(s["heading"], 12, bold=True, color=(0.08, 0.5, 0.24))
        if s.get("note"):
            pdf.wrap(s["note"], 8, color=(0.35, 0.45, 0.4))
        pdf.table(s["columns"], s["rows"])
    return pdf.output()


# ---------------------------------------------------------------------------
# Tableau / BI extract: tidy CSV tables in one ZIP (see docs/TABLEAU_GUIDE.md)
# ---------------------------------------------------------------------------
def tableau_extract():
    import zipfile
    from .models import Alert, SensorReading

    t = datasources.temperature().rename(columns={"Country": "country", "ISO2": "iso2", "ISO3": "iso3",
                                                  "anomaly": "temp_change_degC"})
    t["area_type"] = t["is_region"].map({True: "region", False: "country"})
    t = t.drop(columns=["is_region"])
    d = datasources.disasters().rename(columns={"Country": "country", "ISO2": "iso2", "ISO3": "iso3",
                                                "kind": "disaster_type", "count": "disasters"})
    r = datasources.readings_frame()
    if not r.empty:
        r["timestamp"] = r["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        r = r.rename(columns={"temperature": "temperature_degC", "rainfall": "rainfall_mm",
                              "humidity": "humidity_pct", "co2": "co2_ppm"})
    a = list(Alert.objects.values("created", "severity", "category", "title", "location", "value"))
    countries = t[["country", "iso2", "iso3", "area_type"]].drop_duplicates()

    readme = ("EarthScape Tableau extract\n"
              f"Generated {datetime.now():%Y-%m-%d %H:%M}\n\n"
              "fact_temperature.csv  country/region x year temperature change vs 1951-1980 (degC), REAL (FAO)\n"
              "fact_disasters.csv    country x year x disaster type counts, REAL (EM-DAT)\n"
              "fact_readings.csv     station observations; column 'source' says live/api/upload/sample\n"
              "fact_alerts.csv       alerts raised by EarthScape\n"
              "dim_country.csv       join key: iso3\n\n"
              "Relationships: fact_temperature.iso3 = dim_country.iso3 = fact_disasters.iso3; join year where needed.\n")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme)
        z.writestr("fact_temperature.csv", t.to_csv(index=False))
        z.writestr("fact_disasters.csv", d.to_csv(index=False))
        z.writestr("fact_readings.csv", r.to_csv(index=False))
        z.writestr("dim_country.csv", countries.to_csv(index=False))
        sio = io.StringIO()
        w = csv.writer(sio)
        w.writerow(["created_utc", "severity", "category", "title", "location", "value"])
        for row in a:
            w.writerow([row["created"].strftime("%Y-%m-%dT%H:%M:%SZ"), row["severity"], row["category"],
                        row["title"], row["location"], row["value"]])
        z.writestr("fact_alerts.csv", sio.getvalue())
    return buf.getvalue()
