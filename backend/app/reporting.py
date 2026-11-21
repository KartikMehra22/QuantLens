"""Printable portfolio report with explicit dates, units and model limitations."""

import io
from datetime import datetime, timezone
from html import escape

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def portfolio_pdf(data, evaluation=None):
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    story = []

    def text(value, style="Normal"):
        story.append(Paragraph(escape(str(value)), styles[style]))
        story.append(Spacer(1, 7))

    def table(rows, widths):
        obj = Table(
            [[Paragraph(escape(str(v)), styles["Normal"]) for v in row] for row in rows],
            colWidths=widths,
            repeatRows=1,
            hAlign="LEFT",
        )
        obj.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3ECE8")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([obj, Spacer(1, 12)])

    text("QuantLens portfolio risk report", "Title")
    text(data["name"], "Heading2")
    text(
        f"Closing date {data['as_of']} | Source {data['data_mode']} | Generated {datetime.now(timezone.utc).date()}"
    )
    text(
        f"Value INR {data['value']:,.2f} | Invested INR {data['invested']:,.2f} | Unrealized P&L INR {data['pnl']:,.2f}"
    )
    text(
        f"Simulation period {data.get('period_start', 'unavailable')} to {data.get('period_end', 'unavailable')}"
    )
    table(
        [["Instrument", "Quantity", "Close INR", "Value INR", "Weight"]]
        + [
            [
                h["symbol"],
                f"{h['quantity']:g}",
                f"{h['price']:,.2f}",
                f"{h['value']:,.2f}",
                f"{h['weight']:.2%}",
            ]
            for h in data["holdings"]
        ],
        [100, 70, 95, 110, 75],
    )
    if data["metrics"]:
        m = data["metrics"]
        text("Historical risk measures", "Heading2")
        rows = [["Measure", "Estimate", "Interpretation"]]
        for label, key, meaning in [
            ("Annual volatility", "annualized_volatility", "Annualized daily variability"),
            ("Maximum drawdown", "max_drawdown", "Largest peak-to-trough simulated loss"),
            ("Historical VaR 95%", "var_95", "One-day loss threshold"),
            ("Historical CVaR 95%", "cvar_95", "Mean loss of worst 5% probability mass"),
            ("Annualized growth", "cagr", "Hypothetical geometric annual growth"),
        ]:
            rows.append([label, f"{m[key]:.2%}", meaning])
        rows.append(
            [
                "Sharpe ratio",
                "Unavailable" if m["sharpe_ratio"] is None else f"{m['sharpe_ratio']:.3f}",
                "6% effective annual risk-free assumption",
            ]
        )
        table(rows, [130, 80, 240])
        text(
            f"Sample: {m['observations']} aligned daily returns. Figures are retrospective estimates, not maximum possible losses."
        )
    if data["series"]:
        text("Hypothetical growth from 100", "Heading2")
        drawing = Drawing(450, 120)
        chart = LinePlot()
        chart.x = 40
        chart.y = 20
        chart.width = 390
        chart.height = 90
        chart.data = [[(n, p["value"]) for n, p in enumerate(data["series"])]]
        chart.lines[0].strokeColor = colors.HexColor("#306B54")
        chart.lines[0].strokeWidth = 1.3
        chart.xValueAxis.visible = False
        drawing.add(chart)
        story.append(drawing)
    story.append(PageBreak())
    text("Benchmark and model context", "Heading1")
    b = data.get("benchmark", {})
    if b.get("available"):
        text(f"Nifty 50 comparison {b['start']} to {b['end']}", "Heading2")
        table(
            [
                ["Portfolio price return", "Nifty 50 price return", "Difference pp"],
                [
                    f"{b['portfolio_return']:.2%}",
                    f"{b['benchmark_return']:.2%}",
                    f"{b['difference'] * 100:.2f}",
                ],
            ],
            [150, 160, 140],
        )
        text(b["basis"])
        text(
            "Benchmark comparison excludes dividends on both sides; the main risk view uses adjusted-close returns. Benchmark dates can differ when observations are missing."
        )
    else:
        text("Nifty 50 benchmark unavailable: " + b.get("reason", "No benchmark data for this source."))
    if evaluation:
        e = evaluation.payload
        text("Latest completed rolling evaluation", "Heading2")
        text(
            f"{e['training_window']} training returns | {e['test_days']} targets | Source {e['data_mode']} | {e['evaluation_dates'][0]} to {e['evaluation_dates'][-1]}"
        )
        table(
            [["Model", "MAE", "RMSE", "QLIKE"]]
            + [
                [name, f"{v['mae']:.4e}", f"{v['rmse']:.4e}", f"{v['qlike']:.4f}"]
                for name, v in e["metrics"].items()
            ],
            [150, 100, 100, 100],
        )
        text(
            "Losses use decimal daily variance and squared daily returns as a noisy proxy. Lower is better; QLIKE = mean(log(h) + r squared / h) may be negative. This saved run reflects its original holdings and dates, which may differ from the current portfolio."
        )
    else:
        text(
            "No completed saved model evaluation. Run Analytics > Evaluation to compare models on unseen target days."
        )
    text("Methodology and limitations", "Heading2")
    text(data["methodology"])
    for warning in data["warnings"]:
        text(warning)
    text(
        "Current share quantities and purchase costs are entered by the user. This report does not reconstruct transactions or realized returns. Dividend-adjusted price history does not update the user's share quantities automatically. Forecasts estimate variability and do not predict stock prices. Educational analysis; no investment advice or trade execution."
    )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawString(42, 24, f"QuantLens | {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=38,
        bottomMargin=40,
        title="QuantLens portfolio risk report",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
