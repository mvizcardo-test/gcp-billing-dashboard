import json
import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_NAMES = {
    "contigoapp-prod":           "ContigoApp",
    "backupmv":                  "BackupMV",
    "stocktracker-presentacion": "StockTracker Pro",
    "taf-gobierno-de-datos":     "TAF - Gobierno de Datos",
}

# SQL expression for net cost (usage cost minus credits)
_NET_COST = (
    "SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))"
)


def _bq_client() -> bigquery.Client:
    creds_info = json.loads(st.secrets["gcp"]["credentials_json"])
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(
        credentials=credentials,
        project=st.secrets["gcp"]["bq_project"],
    )


def _table() -> str:
    s = st.secrets["gcp"]
    return f"`{s['bq_project']}.{s['bq_dataset']}.{s['bq_table']}`"


def _add_app_name(df: pd.DataFrame) -> pd.DataFrame:
    df["app_name"] = df["project_id"].map(PROJECT_NAMES).fillna(df["project_id"])
    return df


@st.cache_data(ttl=86400)
def get_costs_by_project(days: int = 30) -> pd.DataFrame:
    query = f"""
    SELECT
        project.id                AS project_id,
        currency,
        ROUND({_NET_COST}, 2)    AS net_cost
    FROM {_table()}
    WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    GROUP BY project.id, currency
    ORDER BY net_cost DESC
    """
    df = _bq_client().query(query).to_dataframe(create_bqstorage_client=False)
    return _add_app_name(df)


@st.cache_data(ttl=86400)
def get_costs_by_service(days: int = 30) -> pd.DataFrame:
    query = f"""
    SELECT
        project.id                AS project_id,
        service.description       AS service,
        currency,
        ROUND({_NET_COST}, 2)    AS net_cost
    FROM {_table()}
    WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    GROUP BY project.id, service, currency
    ORDER BY net_cost DESC
    """
    df = _bq_client().query(query).to_dataframe(create_bqstorage_client=False)
    return _add_app_name(df)


@st.cache_data(ttl=86400)
def get_daily_trend(days: int = 30) -> pd.DataFrame:
    query = f"""
    SELECT
        DATE(usage_start_time)    AS date,
        project.id                AS project_id,
        currency,
        ROUND({_NET_COST}, 2)    AS net_cost
    FROM {_table()}
    WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    GROUP BY date, project.id, currency
    ORDER BY date ASC
    """
    df = _bq_client().query(query).to_dataframe(create_bqstorage_client=False)
    return _add_app_name(df)
