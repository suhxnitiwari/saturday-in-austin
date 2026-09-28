"""Three countries, eight homes: the places Suhani has lived, analyzed with pandas and matplotlib.

  pandas      read the CSV, parse dates, add computed columns, filter, group, aggregate
  matplotlib  a timeline chart in her website palette
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data" / "places_lived.csv"


def load(path: Path = DATA, today=None) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["start", "end"])
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.today().normalize()
    df["current"] = df["end"].isna()
    df["end"] = df["end"].fillna(today)  # still living in Austin, so the stay runs through today
    df["years"] = ((df["end"] - df["start"]).dt.days / 365.25).round(1)
    df["abroad"] = df["country"] != "United States"
    return df


def summary(df: pd.DataFrame) -> dict:
    by_country = (df.groupby("country", sort=False)
                    .agg(homes=("place", "count"), years=("years", "sum"))
                    .round(1))
    longest = df.loc[df["years"].idxmax()]
    return {
        "homes": len(df),
        "countries": df["country"].nunique(),
        "continents": 2,  # Asia and North America
        "by_country": by_country,
        "longest": (longest["place"], float(longest["years"])),
        "india_cities": df.loc[df["country"] == "India", "place"].tolist(),
        "us_years": round(float(df.loc[~df["abroad"], "years"].sum()), 1),
    }


def chart(df: pd.DataFrame, path: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    colors = {"India": "#8F4661", "Singapore": "#E8B86B", "United States": "#F6B8C8"}
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    fig.patch.set_facecolor("#FBF3EE")
    ax.set_facecolor("#FBF3EE")

    rows = df.iloc[::-1].reset_index(drop=True)  # first home at the top
    for i, row in rows.iterrows():
        start = mdates.date2num(row["start"])
        width = mdates.date2num(row["end"]) - start
        ax.barh(i, width, left=start, height=0.62, color=colors[row["country"]])
        label = f"{row['place']}  ·  {row['years']:g} yr" + ("  (now)" if row["current"] else "")
        ax.text(start + width + 60, i, label, va="center", fontsize=9, color="#2A1810")

    ax.set_yticks([])
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.YearLocator(4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(mdates.date2num(df["start"].min()) - 120, mdates.date2num(df["end"].max()) + 1100)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title("3 countries, 8 homes, 1 very adaptable girl", loc="left",
                 fontsize=13, color="#2A1810", fontfamily="serif")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    ax.legend(handles, colors.keys(), frameon=False, loc="upper right", fontsize=8)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
