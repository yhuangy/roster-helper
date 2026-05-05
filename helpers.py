import io
import re
import pandas as pd


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_for_search(value):
    text = clean_text(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text


def read_uploaded_file(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    raise ValueError("Please upload a CSV or Excel file.")


def guess_column(columns, keywords):
    lower_map = {col: str(col).lower() for col in columns}

    for col, lower_col in lower_map.items():
        if all(keyword in lower_col for keyword in keywords):
            return col

    for col, lower_col in lower_map.items():
        if any(keyword in lower_col for keyword in keywords):
            return col

    return columns[0] if len(columns) > 0 else None


def build_roster(df, matric_col, nus_id_col, name_col, seat_col):
    roster = pd.DataFrame({
        "matriculation_number": df[matric_col].apply(clean_text),
        "nus_id": df[nus_id_col].apply(clean_text),
        "student_name": df[name_col].apply(clean_text),
        "original_seat": df[seat_col].apply(clean_text),
    })

    roster["current_seat"] = roster["original_seat"]
    roster["seat_changed"] = False
    roster["last_updated"] = ""

    return roster


def search_roster(roster, query):
    query_clean = normalize_for_search(query)

    if not query_clean:
        return roster.iloc[0:0]

    searchable = (
        roster["matriculation_number"].apply(normalize_for_search)
        + " "
        + roster["nus_id"].apply(normalize_for_search)
        + " "
        + roster["student_name"].apply(normalize_for_search)
    )

    return roster[searchable.str.contains(re.escape(query_clean), na=False)]

def format_display(df):
#    return df.rename(columns={
#        "matriculation_number": "Matric Number",
#        "nus_id": "NUS ID",
#       "student_name": "Student",
#        "original_seat": "Original Seat",
#        "current_seat": "Current Seat",
#        "seat_changed": "Seat Changed",
#        "last_updated": "Last Updated",
#    })
    return df