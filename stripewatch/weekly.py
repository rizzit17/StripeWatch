"""Weekly aggregation module: groups shipments into Monday-start weeks and computes ratio of sums."""
import pandas as pd


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Group shipments into Monday-aligned weeks and compute weekly cost per tonne-km (ratio of sums).

    Args:
        df: DataFrame of validated shipment records with columns:
            origin, destination, route_type, quantity_tonnes, distance_km, freight_cost_inr, shipment_date

    Returns:
        DataFrame with columns: route, route_type, week_of, cost, tonne_km, n_shipments, c
        Sorted by route and week_of.
    """
    data = df.copy()
    if "route" not in data.columns:
        data["route"] = data["origin"].str.strip() + "-" + data["destination"].str.strip()

    # Align each shipment date to Monday of that week
    data["week_of"] = (
        data["shipment_date"] - pd.to_timedelta(data["shipment_date"].dt.weekday, unit="D")
    ).dt.normalize()

    # Tonne-km per shipment
    data["tk"] = data["quantity_tonnes"] * data["distance_km"]

    # Ratio of sums: sum(freight_cost) / sum(tonne_km)
    w = data.groupby(["route", "route_type", "week_of"], as_index=False).agg(
        cost=("freight_cost_inr", "sum"),
        tonne_km=("tk", "sum"),
        n_shipments=("tk", "size")
    )
    w["c"] = w["cost"] / w["tonne_km"]

    # Verify all week_of dates are Mondays (weekday == 0)
    if (w["week_of"].dt.weekday != 0).any():
        raise ValueError("Detected non-Monday week_of date in weekly aggregation")

    w = w.sort_values(["route", "week_of"]).reset_index(drop=True)
    return w
