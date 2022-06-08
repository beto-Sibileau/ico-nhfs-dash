# %%
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from difflib import get_close_matches
from geojson_rewind import rewind
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

# %%
# read source data
file_urls = [
    "https://github.com/beto-Sibileau/ico-nhfs-dash/raw/main/NFHS_data/NFHS345.xlsx",
    "https://github.com/beto-Sibileau/ico-nhfs-dash/raw/main/NFHS_data/NFHS45%20CoC%20and%20Child%20Nutrition.xlsx",
    "https://github.com/beto-Sibileau/ico-nhfs-dash/raw/main/NFHS_data/NFHS-%205%20compiled%20factsheet%20for%20INDIA.xlsx",
    "https://github.com/beto-Sibileau/ico-nhfs-dash/raw/main/NFHS_data/Equity%20Analysis.xlsx",
]
df_list = [
    pd.read_excel(url, sheet_name=0, dtype=str)
    if "Equity" not in url
    else pd.read_excel(url, sheet_name=None, dtype=str, header=2)
    for url in file_urls
]

# %%
# compiled india xls: transform column names
df_list[2].rename(
    columns={
        "Sl.No": "No.",
        "NFHS-5 (2019-21)": "Urban",
        "Unnamed: 4": "Rural",
        "Unnamed: 5": "Total",
        "Unnamed: 7": "Indicator Type",
        "Unnamed: 8": "Gender",
        "Unnamed: 9": "NFHS",
        "Unnamed: 10": "Year (give as a period)",
    },
    inplace=True,
)

# add India as state column
df_list[2]["State"] = "India"
# drop first row
df_list[2].drop(0, inplace=True)

# %%
# equity xls: concat excel sheets per added indicator
df_list_equity = []
for name in list(df_list[3].keys())[:6]:
    df_list[3][name]["Indicator"] = name
    df_list_equity.append(
        df_list[3][name]
        .rename(
            columns={
                "Unnamed: 0": "State",
                "Unnamed: 1": "Total",
            }
        )
        .dropna(subset=["State", "Year"])
    )

df_equity = (
    pd.concat(df_list_equity, ignore_index=True)
    .replace(
        {
            "Indicator": {"Protected against neonatTetnus ": "Neonatal Protection"},
            "Year": {
                "2015-16": "NFHS-4 (2015-16)",
                "2019-21": "NFHS-5 (2019-21)",
                "2019-2021": "NFHS-5 (2019-21)",
            },
            "State": {
                "India": "All India",
                "Jammu And Kashmir": "Jammu and Kashmir",
                "Andaman And Nicobar Islands": "Andaman and Nicobar Islands",
                "Andaman & Nicobar Isl": "Andaman and Nicobar Islands",
                "Dadra & Nagar Haveli": "Dadra and Nagar Haveli",
                "Delhi": "Nct of Delhi",
                "Nct Of Delhi": "Nct of Delhi",
            },
        }
    )
    .astype(
        {
            "Total": "float64",
            "Rural": "float64",
            "Urban": "float64",
            "Poorest": "float64",
            "Poor": "float64",
            "Middle": "float64",
            "Rich": "float64",
            "Richest": "float64",
            "No education": "float64",
            "Primary education": "float64",
            "Secondary education": "float64",
            "Higher education": "float64",
            "SC": "float64",
            "ST": "float64",
            "OBC": "float64",
            "Others": "float64",
            "Hindu": "float64",
            "Muslim": "float64",
            "Other": "float64",
        }
    )
)

# names to display in dropdown equity
states_4_equity = df_equity.State.unique()

# %%
# geojson all
json_file_url = "https://github.com/beto-Sibileau/ico-nhfs-dash/raw/main/shapefiles/India_707_districts_with_J%26K_Adjustment.json"
response_geo = requests.get(json_file_url)
json_read = response_geo.json()
geo_json_dict = rewind(json_read, rfc7946=False)

# %%
# district naming
district_list = [
    dist_name["properties"]["707_dist_7"] for dist_name in geo_json_dict["features"]
]
district_series = pd.Series(district_list)
ds_df = pd.DataFrame(
    {
        "Dist": district_series.str.split(",").str[0],
        "State": district_series.str.split(",").str[1],
    }
)

# %%
# auto match data and GEO states
data_st_dt_df = (
    df_list[1].groupby(["State", "District name"], sort=False, as_index=False).size()
)
data_states = data_st_dt_df.State.unique()
geo_states = ds_df.State.dropna().unique()

state_match = [
    get_close_matches(st.lower(), geo_states, n=1, cutoff=0.5) for st in data_states
]
state_geo_df = pd.DataFrame(
    {"State": data_states, "State_geo": [st[0] if st else np.nan for st in state_match]}
)

# manual adjust after inspection
state_geo_df.loc[state_geo_df.State == "D & D", "State_geo"] = " Daman and Diu"
state_geo_df.loc[
    state_geo_df.State == "D & DNH", "State_geo"
] = " Dadra and Nagar Haveli"

# %%
# auto match data and GEO districts
district_geo_df_list = []
for state in data_states:

    data_districts = data_st_dt_df[data_st_dt_df.State == state]["District name"]
    matched_state = state_geo_df[state_geo_df.State == state].State_geo.values[0]
    geo_districts = ds_df[ds_df.State == matched_state].Dist

    district_match = [
        get_close_matches(dt.lower(), geo_districts, n=1, cutoff=0.5)
        for dt in data_districts
    ]
    district_geo_df = pd.DataFrame(
        {
            "District name": data_districts,
            "District_geo": [st[0] if st else np.nan for st in district_match],
        }
    )
    district_geo_df["State"] = state
    district_geo_df["State_geo"] = matched_state
    district_geo_df_list.append(district_geo_df)

state_district_geo_df = pd.concat(district_geo_df_list, ignore_index=True)

# manual adjust after inspection
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "D & DNH", "District_geo"
] = "Dadra & Nagar Haveli"
print(
    "Ask RAKESH about PRESENCE of District TUE in NAGALAND - NOTE also TUENSANG appears"
)

# manual adjust after inspection for double assigned ones
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East Godavari", "District_geo"
] = "East Godavari"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "Uttara Kannada", "District_geo"
] = "Uttara Kannada"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East Khasi Hills", "District_geo"
] = "East Khasi Hills"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East Garo Hills", "District_geo"
] = "East Garo Hills"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "Imphal East", "District_geo"
] = "Imphal East"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East District", "District_geo"
] = "East District"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "Ranga Reddy", "District_geo"
] = "Ranga Reddy"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East Kameng", "District_geo"
] = "East Kameng"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East Siang", "District_geo"
] = "East Siang"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "East", "District_geo"
] = "East"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "North East", "District_geo"
] = "North East"
state_district_geo_df.loc[
    state_district_geo_df["District name"] == "South East", "District_geo"
] = "South East"

# re-name for geojson: join Distric and Stae geo's
state_district_geo_df.loc[:, "District_geo"] = (
    state_district_geo_df[["District_geo", "State_geo"]]
    .fillna("N/A")
    .agg(",".join, axis=1)
)
# drop state_geo after join no longer needed
state_district_geo_df.drop(columns="State_geo", inplace=True)

# %%
# dictionary for plotly: label with no figure
label_no_fig = {
    "layout": {
        "xaxis": {"visible": False},
        "yaxis": {"visible": False},
        "annotations": [
            {
                "text": "No matching data",
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 28},
            }
        ],
    }
}

# %%
# all india or states list
india_or_state_options = [
    {"label": l, "value": l} for l in sorted(["All India", *data_states], key=str.lower)
]

# dbc select: KPI district map --> All India or States
dd_india_or_state = dbc.Select(
    id="india-or-state-dd",
    size="sm",
    options=india_or_state_options,
    value="Kerala",
)

# %%
# district map indicators list
district_kpi_map = df_list[1].columns[4:].values
district_map_options = [
    {"label": l, "value": l} for l in sorted(district_kpi_map, key=str.lower)
]

# dbc select: KPI district map
dd_kpi_map_district = dbc.Select(
    id="kpi-district-map-dd",
    size="sm",
    options=district_map_options,
    value=district_kpi_map[0],
)

# %%
# hard code indicator list color: inverse
kpi_color_inverse = [
    "Women age 20-24 years married before age 18 years (%)",
    "Total unmet need (%)",
    "Unmet need for spacing(%)",
    "Births delivered by caesarean section (%)",
    "Births in a private health facility that were delivered by caesarean section %)",
    "Births in a public health facility that were delivered by caesarean section (%)",
    "Children under 5 years who are stunted (height-for-age) (%)",
    "Children under 5 years who are wasted (weight-for-height) (%)",
    "Children under 5 years who are underweight (weight-for-age) (%)",
    "Children under 5 years who are overweight (weight-for-height) (%)",
    "Children age 6-59 months who are anaemic (<11.0 g/dl) (%)",
    "All women age 15-49 years who are anaemic (%)",
    "All women age 15-19 years who are anaemic (%) ",
]

# %%
# # NFHS round
# nfhs_rounds = df_list[1].Round.unique()
# nfhs_options = [{"label": l, "value": l} for l in nfhs_rounds]

# # dbc select: KPI district map --> NFHS round
# dd_nfhs_round = dbc.Select(
#     id="nfhs-round-dd",
#     options=nfhs_options,
#     value=nfhs_rounds[-1],
# )

# %%
# dbc district kpi map row
district_map_row = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select All India or State",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "16px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_india_or_state,
                        ]
                    ),
                    width="auto",
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select KPI",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "16px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_kpi_map_district,
                        ]
                    ),
                    width="auto",
                ),
                # dbc.Col(
                #     html.Div([
                #         html.P(
                #             "Select NFHS Round",
                #             style={
                #                 'fontWeight': 'bold', # 'normal', #
                #                 'textAlign': 'left', # 'center', #
                #                 # 'paddingTop': '25px',
                #                 'color': 'DeepSkyBlue',
                #                 'fontSize': '16px',
                #                 'marginBottom': '10px',
                #             }
                #         ),
                #         dd_nfhs_round
                #     ]),
                #     width="auto"
                # ),
            ],
            justify="evenly",
            align="center",
            style={
                # 'paddingLeft': '25px',
                "marginBottom": "30px",
            },
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "NFHS-4 (2015-16)",
                                style={
                                    "fontWeight": "normal",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "Blue",
                                    "fontSize": "16px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dcc.Graph(id="district-plot", figure=label_no_fig),
                        ]
                    ),
                    width=5,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "NFHS-5 (2019-21)",
                                style={
                                    "fontWeight": "normal",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "Blue",
                                    "fontSize": "16px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dcc.Graph(id="district-plot-r2", figure=label_no_fig),
                        ]
                    ),
                    width=5,
                ),
            ],
            justify="evenly",
            align="center",
        ),
    ],
    fluid=True,
)

# %%
# df for district map with added column for geo_json
district_map_df = (
    df_list[1]
    .melt(id_vars=["State", "District name", "Round", "year"])
    .merge(
        state_district_geo_df,
        on=["State", "District name"],
        how="left",
        sort=False,
    )
)

filter_na = district_map_df.value.isnull()
filter_non_num = pd.to_numeric(district_map_df.value, errors="coerce").isnull()
# negatives detected
print("Ask RAKESH about PRESENCE of NON-NUMERICS")
print(district_map_df[filter_non_num & ~filter_na].values[0])
# drop non-num
district_map_df = (
    district_map_df.drop(district_map_df[filter_non_num & ~filter_na].index)
    .astype({"value": "float64"})
    .reset_index(drop=True)
)

filter_negative = district_map_df.value < 0
# negatives detected
print("Ask RAKESH about PRESENCE of NEGATIVES")
print(district_map_df[filter_negative].values[0])
# drop negatives
district_map_df = district_map_df.drop(
    district_map_df[filter_negative].index
).reset_index(drop=True)

# %%
# filter geojson by state
geo_dict = {}
for state in data_states:
    matched_state = state_geo_df[state_geo_df.State == state].State_geo.values[0]
    featured_list = [
        feature
        for feature in geo_json_dict["features"]
        if matched_state in feature["properties"]["707_dist_7"]
    ]
    geo_dict[state] = featured_list

# %%
# filter available district geo's
district_geo_dict = {}
for state in data_states:
    featured_df = state_district_geo_df.query("State == @state").reset_index(drop=True)
    district_geo_dict[state] = featured_df
district_geo_dict["All India"] = state_district_geo_df

# %%
# states list
state_options = [{"label": l, "value": l} for l in sorted(data_states, key=str.lower)]
# dcc dropdown: states --> dcc allows multi, styling not as dbc
dd_states = dcc.Dropdown(
    id="my-states-dd",
    options=state_options,
    value="Kerala",
    multi=True,
)

# dbc select: district scatter list 1
dd_district_list_1 = dbc.Select(
    id="kpi-district-list-1",
    size="sm",
    options=district_map_options,
    value=district_kpi_map[10],
)

# dbc select: district scatter list 2
dd_district_list_2 = dbc.Select(
    id="kpi-district-list-2",
    size="sm",
    options=district_map_options,
    value=district_kpi_map[14],
)

# %%
# dbc district scatter row
district_scatter_row = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select State/s",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "14px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_states,
                        ],
                        style={"font-size": "75%"},
                    ),
                    width=2,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select KPI 1",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "14px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_district_list_1,
                        ]
                    ),
                    width=5,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select KPI 2",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "14px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_district_list_2,
                        ]
                    ),
                    width=5,
                ),
            ],
            justify="evenly",
            align="center",
            style={
                # 'paddingLeft': '25px',
                "marginBottom": "25px",
            },
        ),
        # dbc.Row([
        #     dbc.Col(
        #         button_group_nfhs,
        #         width="auto"
        #     ),
        # ], justify="start", align="start", style={'paddingLeft': '25px'}),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(id="district-plot-scatter", figure=label_no_fig), width=6
                ),
                dbc.Col(
                    dcc.Graph(id="district-plot-scatter-2", figure=label_no_fig),
                    width=6,
                ),
            ],
            justify="evenly",
            align="center",
        ),
    ],
    fluid=True,
)

# %%
# filter gender indicators for trend analysis
df_nfhs_345 = (
    pd.concat(
        [
            df_list[0],
            df_list[2][
                ["Indicator", "NFHS-4 (2015-16)", "Indicator Type", "Gender", "State"]
            ].rename(columns={"NFHS-4 (2015-16)": "Total"}),
            df_list[2].drop(columns="NFHS-4 (2015-16)"),
        ],
        ignore_index=True,
    )
    .fillna({"NFHS": "NFHS 4", "Year (give as a period)": "2016"})
    .query("Gender.isnull()", engine="python")
    .reset_index(drop=True)
    .replace({"State": {"INDIA": "India"}})
    .replace({"State": {"India": "All India"}})
)

# retain Indicator Types - Indicator combinations
nfhs_345_ind_df = df_nfhs_345.groupby(
    ["Indicator Type", "Indicator"], sort=False, as_index=False
).size()

# states or india: nfhs_345 list
nfhs_345_states = sorted(df_nfhs_345.State.unique(), key=str.lower)

# %%
# filter uncleaned data in numerical columns
num_cols = ["Urban", "Rural", "Total"]
for col in num_cols:
    filter_na_345 = df_nfhs_345[col].isnull()
    filter_non_num_345 = pd.to_numeric(df_nfhs_345[col], errors="coerce").isnull()
    # non numerics
    print("Ask RAKESH about PRESENCE of NON-NUMERICS")
    print(df_nfhs_345[filter_non_num_345 & ~filter_na_345][col].values[0])
    # drop non-num
    df_nfhs_345 = (
        df_nfhs_345.drop(df_nfhs_345[filter_non_num_345 & ~filter_na_345].index)
        .astype({col: "float64"})
        .reset_index(drop=True)
    )

    # negatives detected
    filter_neg_345 = df_nfhs_345[col] < 0
    print("Ask RAKESH about PRESENCE of NEGATIVES")
    print(
        f"No negatives for df column {col}"
        if df_nfhs_345[filter_neg_345].empty
        else df_nfhs_345[filter_neg_345].values[0]
    )
    # drop negatives
    df_nfhs_345 = df_nfhs_345.drop(df_nfhs_345[filter_neg_345].index).reset_index(
        drop=True
    )

# %%
# dcc dropdown: nfhs 345 states --> dcc allows multi, styling not as dbc
dd_state_4_trend = dcc.Dropdown(
    id="state-trend-dd",
    options=[{"label": l, "value": l} for l in nfhs_345_states],
    value="Kerala",
    multi=True,
)

# initial indicator type
ini_ind_type = "Population and Household Profile"
# dcc dropdown: nfhs 345 indicator type --> dcc allows multi, styling not as dbc
dd_indicator_type = dcc.Dropdown(
    id="indicator-type-dd",
    options=[
        {"label": l, "value": l}
        for l in sorted(nfhs_345_ind_df["Indicator Type"].unique(), key=str.lower)
    ],
    value=ini_ind_type,
    multi=True,
)

# dcc dropdown: nfhs 345 indicators --> dcc allows multi, styling not as dbc
ini_indicators_345 = sorted(
    nfhs_345_ind_df.query("`Indicator Type` == @ini_ind_type").Indicator.values,
    key=str.lower,
)
dd_indicator_345 = dcc.Dropdown(
    id="indicator-345-dd",
    options=[{"label": l, "value": l} for l in ini_indicators_345],
    value=ini_indicators_345[0],
    multi=True,
)

# %%
# dbc state trends row
state_trend_row = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select India and/or State/s",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "14px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_state_4_trend,
                        ],
                        style={"font-size": "75%"},
                    ),
                    width=2,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select Indicator Type",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "14px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_indicator_type,
                        ],
                        style={"font-size": "85%"},
                    ),
                    width=4,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select KPI",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "14px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_indicator_345,
                        ],
                        style={"font-size": "85%"},
                    ),
                    width=6,
                ),
            ],
            justify="evenly",
            align="center",
            style={
                # 'paddingLeft': '25px',
                "marginBottom": "25px",
            },
        ),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(id="state-trend-plot", figure=label_no_fig), width=12
                ),
            ],
            justify="evenly",
            align="center",
        ),
    ],
    fluid=True,
)

# %%
# dbc select: all india or states for equity
union_territories = [
    "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli",
    "Daman and Diu",
    "Chandigarh",
    "Lakshadweep",
    "Puducherry",
    "Ladakh",
]

dd_states_equity = dbc.Select(
    id="dd-states-equity",
    options=[
        {"label": l, "value": l}
        for l in sorted(states_4_equity, key=str.lower)
        if l not in union_territories
    ],
    value="All India",
)

# %%
# dbc ButtonGroup with RadioItems
button_group_disagg = html.Div(
    [
        dbc.RadioItems(
            id="radios-disagg",
            className="btn-group",
            inputClassName="btn-check",
            labelClassName="btn btn-outline-info",
            labelCheckedClassName="active",
            options=[
                {"label": "Residence", "value": "Residence"},
                {"label": "Wealth", "value": "Wealth"},
                {"label": "Women's Education", "value": "Women's Education"},
                {"label": "Caste", "value": "Caste"},
                {"label": "Religion", "value": "Religion"},
            ],
            value="Residence",
        ),
    ],
    className="radio-group",
)

# %%
# dbc states equity bar row
state_equity_row = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select All India or State",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "16px",
                                    "marginBottom": "10px",
                                },
                            ),
                            dd_states_equity,
                        ]
                    ),
                    width="auto",
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.P(
                                "Select Disaggregation",
                                style={
                                    "fontWeight": "bold",  # 'normal', #
                                    "textAlign": "left",  # 'center', #
                                    # 'paddingTop': '25px',
                                    "color": "DeepSkyBlue",
                                    "fontSize": "16px",
                                    "marginBottom": "10px",
                                },
                            ),
                            button_group_disagg,
                        ]
                    ),
                    width="auto",
                ),
            ],
            justify="evenly",
            align="center",
            style={
                # 'paddingLeft': '25px',
                "marginBottom": "30px",
            },
        ),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(id="state-equity-plot", figure=label_no_fig), width=6
                ),
                dbc.Col(
                    dcc.Graph(id="state-equity-plot-2", figure=label_no_fig), width=6
                ),
            ],
            justify="evenly",
            align="center",
        ),
    ],
    fluid=True,
)

# %%
fontawesome_stylesheet = "https://use.fontawesome.com/releases/v5.8.1/css/all.css"
# Build App
app = Dash(
    __name__, external_stylesheets=[dbc.themes.BOOTSTRAP, fontawesome_stylesheet]
)

# to deploy using WSGI server
server = app.server
# app tittle for web browser
app.title = "NFHS"

# title row
title_row = dbc.Container(
    dbc.Row(
        [
            dbc.Col(
                html.Img(src="assets/logo-unicef-large.svg"),
                width=3,
                # width={"size": 3, "offset": 1},
                style={"paddingLeft": "20px", "paddingTop": "20px"},
            ),
            dbc.Col(
                html.Div(
                    [
                        html.H6(
                            "National Family Health Survey",
                            style={
                                "fontWeight": "bold",
                                "textAlign": "center",
                                "paddingTop": "25px",
                                "color": "white",
                                "fontSize": "32px",
                            },
                        ),
                    ]
                ),
                # width='auto',
                width={"size": "auto", "offset": 1},
            ),
        ],
        justify="start",
        align="center",
    ),
    fluid=True,
)

# App Layout
app.layout = html.Div(
    [
        # title Div
        html.Div(
            [title_row],
            style={
                "height": "100px",
                "width": "100%",
                "backgroundColor": "DeepSkyBlue",
                "margin-left": "auto",
                "margin-right": "auto",
                "margin-top": "15px",
            },
        ),
        # div district map row
        dcc.Loading(
            children=html.Div(
                [district_map_row],
                style={
                    "paddingTop": "20px",
                },
            ),
            id="loading-map",
            type="circle",
            fullscreen=True,
        ),
        html.Hr(
            style={
                "color": "DeepSkyBlue",
                "height": "3px",
                "margin-top": "30px",
                "margin-bottom": "0",
            }
        ),
        # div scatter row (no loading added)
        html.Div(
            [district_scatter_row],
            style={
                "paddingTop": "20px",
            },
        ),
        html.Hr(
            style={
                "color": "DeepSkyBlue",
                "height": "3px",
                "margin-top": "30px",
                "margin-bottom": "0",
            }
        ),
        # div trend row (no loading added)
        html.Div(
            [state_trend_row],
            style={
                "paddingTop": "20px",
            },
        ),
        html.Hr(
            style={
                "color": "DeepSkyBlue",
                "height": "3px",
                "margin-top": "30px",
                "margin-bottom": "0",
            }
        ),
        # div equity row (no loading added)
        html.Div(
            [state_equity_row],
            style={
                "paddingTop": "20px",
            },
        ),
    ]
)

# %%
# function to avoid figure display inline
def update_cm_fig(cm_fig):
    cm_fig.update_geos(fitbounds="locations", visible=False)
    cm_fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    return cm_fig


# color names for scale
color_names = ["Navy", "FloralWhite", "DarkRed"]
# customed continous scale
red_y_blue = [[0, color_names[0]], [0.5, color_names[1]], [1, color_names[2]]]
# customed continous scale: gray NaNs
color_nan = "gray"
nan_blue_y_red = [
    [0, color_nan],
    [0.001, color_nan],
    [0.001, color_names[0]],
    [0.5, color_names[1]],
    [1, color_names[2]],
]
nan_red_y_blue = [
    [0, color_nan],
    [0.001, color_nan],
    [0.001, color_names[2]],
    [0.5, color_names[1]],
    [1, color_names[0]],
]


@app.callback(
    Output("district-plot", "figure"),
    Output("district-plot-r2", "figure"),
    Input("india-or-state-dd", "value"),
    Input("kpi-district-map-dd", "value"),
    # Input('nfhs-round-dd', 'value'),
)
# use dropdown values: update geo-json and indicator in map (district-wise)
def disp_in_district_map(india_or_state, distr_kpi):

    # test if all_india
    if india_or_state == "All India":
        # query dataframe
        display_df = district_map_df.query(
            "variable == @distr_kpi & Round == 'NFHS-4'"
        ).reset_index(drop=True)
        display_df_r2 = district_map_df.query(
            "variable == @distr_kpi & Round == 'NFHS-5'"
        ).reset_index(drop=True)
        # do not filter geojson
        geofile = geo_json_dict
    else:
        # query dataframe
        display_df = district_map_df.query(
            "State == @india_or_state & variable == @distr_kpi & Round == 'NFHS-4'"
        ).reset_index(drop=True)
        display_df_r2 = district_map_df.query(
            "State == @india_or_state & variable == @distr_kpi & Round == 'NFHS-5'"
        ).reset_index(drop=True)
        # filter geojson by state
        geofile = {}
        geofile["type"] = "FeatureCollection"
        geofile["features"] = geo_dict[india_or_state]

    # min-max block kpis - before setting missing as negatives
    district_kpi_min = display_df.value.min()
    district_kpi_max = display_df.value.max()
    # min-max block kpis - before setting missing as negatives
    district_kpi_min_2 = display_df_r2.value.min()
    district_kpi_max_2 = display_df_r2.value.max()
    # use same range to compare rounds
    full_range = [
        pd.Series([district_kpi_min, district_kpi_min_2]).min() - 0.1,
        pd.Series([district_kpi_max, district_kpi_max_2]).max(),
    ]

    # set missing reporting districts
    not_reported = np.setdiff1d(
        district_geo_dict[india_or_state]["District name"].values,
        display_df["District name"].values,
    )
    not_reported_geo = [
        district_geo_dict[india_or_state]
        .query("`District name` == @a_name")
        .District_geo.values[0]
        for a_name in not_reported
    ]
    # concat not_reported as negatives
    display_df = pd.concat(
        [
            display_df,
            pd.DataFrame(
                {
                    "District_geo": not_reported_geo,
                    "District_name": not_reported,
                }
            ),
        ],
        ignore_index=True,
    ).fillna(-1)

    # set missing reporting districts r2
    not_reported_r2 = np.setdiff1d(
        district_geo_dict[india_or_state]["District name"].values,
        display_df_r2["District name"].values,
    )
    not_reported_geo_r2 = [
        district_geo_dict[india_or_state]
        .query("`District name` == @a_name")
        .District_geo.values[0]
        for a_name in not_reported_r2
    ]
    # concat not_reported as negatives
    display_df_r2 = pd.concat(
        [
            display_df_r2,
            pd.DataFrame(
                {
                    "District_geo": not_reported_geo_r2,
                    "District_name": not_reported_r2,
                }
            ),
        ],
        ignore_index=True,
    ).fillna(-1)

    # scale according to indicator
    dyn_color_scale = (
        nan_blue_y_red if distr_kpi in kpi_color_inverse else nan_red_y_blue
    )

    # district map
    cmap_fig = px.choropleth(
        display_df,
        geojson=geofile,
        featureidkey="properties.707_dist_7",  # 'properties.ST_NM', #
        locations="District_geo",
        color="value",
        # color_continuous_scale = "RdBu",
        color_continuous_scale=dyn_color_scale,
        range_color=full_range,
        # color_discrete_map={'red':'red', 'orange':'orange', 'green':'green'},
        # hover_data=[dd_value],
        projection="mercator",
    )

    # district map - round 2
    cmap_fig_r2 = px.choropleth(
        display_df_r2,
        geojson=geofile,
        featureidkey="properties.707_dist_7",  # 'properties.ST_NM', #
        locations="District_geo",
        color="value",
        # color_continuous_scale = "RdBu",
        color_continuous_scale=dyn_color_scale,
        range_color=full_range,
        # color_discrete_map={'red':'red', 'orange':'orange', 'green':'green'},
        # hover_data=[dd_value],
        projection="mercator",
    )

    return update_cm_fig(cmap_fig), update_cm_fig(cmap_fig_r2)


# %%
@app.callback(
    Output("district-plot-scatter", "figure"),
    Output("district-plot-scatter-2", "figure"),
    Input("my-states-dd", "value"),
    Input("kpi-district-list-1", "value"),
    Input("kpi-district-list-2", "value"),
)
def update_scatter(state_values, kpi_1, kpi_2):

    if not state_values:
        return label_no_fig, label_no_fig

    # query dataframe
    kpi_list = [kpi_1, kpi_2]
    display_df = (
        district_map_df.query(
            "State in @state_values & variable in @kpi_list & Round == 'NFHS-4'"
        )
        .pivot(
            index=["State", "District name"],
            columns="variable",
            values="value",
        )
        .reset_index()
    )

    display_df_2 = (
        district_map_df.query(
            "State in @state_values & variable in @kpi_list & Round == 'NFHS-5'"
        )
        .pivot(
            index=["State", "District name"],
            columns="variable",
            values="value",
        )
        .reset_index()
    )

    if display_df.empty or display_df_2.empty:
        return label_no_fig, label_no_fig
    else:
        scatter_fig = (
            px.scatter(
                display_df,
                x=kpi_1,
                y=kpi_2,
                color="State",
                opacity=0.5,
                trendline="ols",
                trendline_scope="overall",
                title="NFHS-4 (2015-16)",
                hover_data=["District name"],
            )
            .update_traces(marker=dict(size=16))
            .update_yaxes(title_font=dict(size=11))
            .update_xaxes(title_font=dict(size=11))
        )
        x_avg = display_df[kpi_1].mean()
        scatter_fig.add_vline(
            x=x_avg, line_dash="dash", line_width=3, line_color="green"
        ).update_traces(line_width=3)
        y_avg = display_df[kpi_2].mean()
        scatter_fig.add_hline(
            y=y_avg, line_dash="dash", line_width=3, line_color="green"
        ).update_traces(line_width=3)

        scatter_fig_2 = (
            px.scatter(
                display_df_2,
                x=kpi_1,
                y=kpi_2,
                color="State",
                opacity=0.5,
                trendline="ols",
                trendline_scope="overall",
                title="NFHS-5 (2019-21)",
                hover_data=["District name"],
            )
            .update_traces(marker=dict(size=16))
            .update_yaxes(title_font=dict(size=11))
            .update_xaxes(title_font=dict(size=11))
        )
        x_avg_2 = display_df_2[kpi_1].mean()
        scatter_fig_2.add_vline(
            x=x_avg_2, line_dash="dash", line_width=3, line_color="green"
        ).update_traces(line_width=3)
        y_avg_2 = display_df_2[kpi_2].mean()
        scatter_fig_2.add_hline(
            y=y_avg_2, line_dash="dash", line_width=3, line_color="green"
        ).update_traces(line_width=3)

        # adjust scales for comparisson
        x_min = display_df[kpi_1].min()
        y_min = display_df[kpi_2].min()
        x_min_2 = display_df_2[kpi_1].min()
        y_min_2 = display_df_2[kpi_2].min()
        x_max = display_df[kpi_1].max()
        y_max = display_df[kpi_2].max()
        x_max_2 = display_df_2[kpi_1].max()
        y_max_2 = display_df_2[kpi_2].max()
        # use same range to compare rounds
        full_range = [
            [
                pd.Series([x_min, x_min_2]).min() * 0.9,
                pd.Series([y_min, y_min_2]).min() * 0.9,
            ],
            [
                pd.Series([x_max, x_max_2]).max() * 1.1,
                pd.Series([y_max, y_max_2]).max() * 1.1,
            ],
        ]
        # update axis in scatters
        scatter_fig.update_xaxes(range=[full_range[0][0], full_range[1][0]])
        scatter_fig.update_yaxes(range=[full_range[0][1], full_range[1][1]])
        scatter_fig_2.update_xaxes(range=[full_range[0][0], full_range[1][0]])
        scatter_fig_2.update_yaxes(range=[full_range[0][1], full_range[1][1]])

    # check for missing reported indicators for NFHS rounds
    plot_1_flag = display_df.dropna(axis=1, how="all").shape[1] < display_df.shape[1]
    plot_2_flag = (
        display_df_2.dropna(axis=1, how="all").shape[1] < display_df_2.shape[1]
    )

    if plot_1_flag & plot_2_flag:
        return label_no_fig, label_no_fig
    elif plot_1_flag:
        r_sq_2 = round(
            px.get_trendline_results(scatter_fig_2).px_fit_results.iloc[0].rsquared, 2
        )
        scatter_fig_2.data[
            -1
        ].hovertemplate = f"<b>OLS trendline</b><br>R<sup>2</sup>={r_sq_2}"
        return label_no_fig, scatter_fig_2
    elif plot_2_flag:
        r_sq = round(
            px.get_trendline_results(scatter_fig).px_fit_results.iloc[0].rsquared, 2
        )
        scatter_fig.data[
            -1
        ].hovertemplate = f"<b>OLS trendline</b><br>R<sup>2</sup>={r_sq}"
        return scatter_fig, label_no_fig
    else:
        r_sq = round(
            px.get_trendline_results(scatter_fig).px_fit_results.iloc[0].rsquared, 2
        )
        scatter_fig.data[
            -1
        ].hovertemplate = f"<b>OLS trendline</b><br>R<sup>2</sup>={r_sq}"
        r_sq_2 = round(
            px.get_trendline_results(scatter_fig_2).px_fit_results.iloc[0].rsquared, 2
        )
        scatter_fig_2.data[
            -1
        ].hovertemplate = f"<b>OLS trendline</b><br>R<sup>2</sup>={r_sq_2}"
        return scatter_fig, scatter_fig_2


# %%
@app.callback(
    Output("indicator-345-dd", "options"),
    Input("indicator-type-dd", "value"),
    prevent_initial_call=True,
)
# update dropdown options: indicator 345 based on indicator type/s
def update_indicator_options(indicator_type):

    if not indicator_type:
        return []

    # dcc dropdown: nfhs 345 indicators --> dcc allows multi, styling not as dbc
    indicators_345 = sorted(
        nfhs_345_ind_df.query("`Indicator Type` in @indicator_type").Indicator.values,
        key=str.lower,
    )
    return [{"label": l, "value": l} for l in indicators_345]


# %%
@app.callback(
    Output("state-trend-plot", "figure"),
    Input("state-trend-dd", "value"),
    Input("indicator-345-dd", "value"),
)
def update_trend(state_values, kpi_values):

    if not state_values or not kpi_values:
        return label_no_fig

    display_df = (
        df_nfhs_345.query("State in @state_values & Indicator in @kpi_values")
        .melt(
            id_vars=["Indicator", "State", "NFHS", "Year (give as a period)"],
            value_vars=["Urban", "Rural", "Total"],
        )
        .sort_values(
            ["Year (give as a period)", "State", "Indicator"],
            ignore_index=True,
        )
        .set_index(["State", "Indicator"])
        .astype({"value": "float64"})
    )

    if display_df.empty:
        return label_no_fig
    else:
        trend_fig = px.line(
            display_df,
            x="Year (give as a period)",
            y="value",
            color=list(display_df.index),
            symbol="variable",
            line_dash="variable",
            line_shape="spline",
            render_mode="svg,",
            hover_data=["NFHS"],
        ).update_traces(mode="lines+markers")

        trend_fig.update_layout(legend=dict(font=dict(size=8), y=0.5, x=1.1))

        return trend_fig
        
# %%
@app.callback(
    Output("state-equity-plot", "figure"),
    Output("state-equity-plot-2", "figure"),
    Input("dd-states-equity", "value"),
    Input("radios-disagg", "value"),
)
def update_equity(state_value, disagg_value):

    if disagg_value == "Residence":
        col_map = ["Total", "Rural", "Urban"]
    elif disagg_value == "Wealth":
        col_map = ["Poorest", "Poor", "Middle", "Rich", "Richest"]
    elif disagg_value == "Women's Education":
        col_map = [
            "No education",
            "Primary education",
            "Secondary education",
            "Higher education",
        ]
    elif disagg_value == "Caste":
        col_map = ["SC", "ST", "OBC", "Others"]
    else:
        col_map = ["Hindu", "Muslim", "Other"]

    display_df = df_equity.query(
        "State == @state_value & Year == 'NFHS-4 (2015-16)'"
    ).melt(
        id_vars=["Indicator", "State"],
        value_vars=col_map,
    )

    display_df_2 = df_equity.query(
        "State == @state_value & Year == 'NFHS-5 (2019-21)'"
    ).melt(
        id_vars=["Indicator", "State"],
        value_vars=col_map,
    )

    fig = px.bar(
        display_df,
        x="Indicator",
        y="value",
        color="variable",
        barmode="group",
        title="NFHS-4 (2015-16)",
    ).update_yaxes(range=[0, 100])

    fig_2 = px.bar(
        display_df_2,
        x="Indicator",
        y="value",
        color="variable",
        barmode="group",
        title="NFHS-5 (2019-21)",
    ).update_yaxes(range=[0, 100])

    return fig, fig_2

# %%
# Run app and print out the application URL
if __name__ == "__main__":
    app.run_server(debug=True)
