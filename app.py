import io
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from pathlib import Path
SAVE_PATH = Path("updated_roster.csv")

from helpers import clean_text, read_uploaded_file, guess_column, build_roster, search_roster, format_display

st.set_page_config(
    page_title="Exam Roster Lookup",
    layout="wide",
)

# -----------------------------
# Helper functions
# -----------------------------

def clean_text(value):
    """Standardize text for matching."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_for_search(value):
    """Lowercase and remove extra spacing for more forgiving search."""
    text = clean_text(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text

def read_uploaded_file(uploaded_file):
    """Read CSV or Excel file."""
    filename = uploaded_file.name.lower()

    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    raise ValueError("Please upload a CSV or Excel file.")

def guess_column(columns, keywords):
    """Try to guess a column based on keywords."""
    lower_map = {col: str(col).lower() for col in columns}

    for col, lower_col in lower_map.items():
        if all(keyword in lower_col for keyword in keywords):
            return col

    for col, lower_col in lower_map.items():
        if any(keyword in lower_col for keyword in keywords):
            return col

    return columns[0] if len(columns) > 0 else None


def build_roster(df, matric_col, nus_id_col, name_col, seat_col):
    """Create the standardized roster used by the app."""
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
    """Search by Matric Number, NUS ID, or Student Name."""
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


def convert_df_to_excel(df):
    """Export dataframe to Excel bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="updated_roster")
    return output.getvalue()

# -----------------------------
# App state
# -----------------------------

if "raw_df" not in st.session_state:
    st.session_state.raw_df = None

if "roster" not in st.session_state:
    if SAVE_PATH.exists():
        st.session_state.roster = pd.read_csv(SAVE_PATH)
    else:
        st.session_state.roster = None

# -----------------------------
# Sidebar: upload and setup
# -----------------------------

st.sidebar.subheader("Upload a seathing arrangement")

uploaded_file = st.sidebar.file_uploader(
    "Upload CSV or Excel file",
    type=["csv", "xlsx", "xls"],
)

if uploaded_file is not None:
    try:
        raw_df = read_uploaded_file(uploaded_file)
        st.session_state.raw_df = raw_df

        st.sidebar.success(f"Loaded: {uploaded_file.name}")

        columns = list(raw_df.columns)

        student_no_guess = guess_column(columns, ["student", "id"])
        if student_no_guess not in columns:
            student_no_guess = guess_column(columns, ["student", "number"])

        name_guess = guess_column(columns, ["name"])
        seat_guess = guess_column(columns, ["seat"])

        matric_col = st.sidebar.selectbox(
            "Matric number",
            columns,
            index=columns.index(student_no_guess) if student_no_guess in columns else 0,
        )

        nus_id_col = st.sidebar.selectbox(
            "NUSID",
            columns,
            index=columns.index("NUS-ID") if "NUS-ID" in columns else 0,
        )
        
        name_col = st.sidebar.selectbox(
            "Student name",
            columns,
            index=columns.index(name_guess) if name_guess in columns else 0,
        )

        seat_col = st.sidebar.selectbox(
            "Seat number column",
            columns,
            index=columns.index(seat_guess) if seat_guess in columns else 0,
        )

        if st.sidebar.button("Create roster", type="primary"):
            roster = build_roster(raw_df, matric_col, nus_id_col, name_col, seat_col)
            st.session_state.roster = roster
            st.sidebar.success("Roster created.")
            roster.to_csv(SAVE_PATH, index=False)

    except Exception as e:
        st.sidebar.error(f"Unable to read file: {e}")

if st.session_state.roster is not None:
    st.sidebar.success(f"Roster ready: {len(st.session_state.roster)} students")

st.sidebar.markdown("---")
if st.sidebar.button("Reset and remove data"):
    st.session_state.raw_df = None
    st.session_state.roster = None
    
    # Remove saved file if it exists
    if SAVE_PATH.exists():
        SAVE_PATH.unlink()
    st.rerun()
    
# -----------------------------
# Main app
# -----------------------------

st.title("Exam Roster Lookup")

st.markdown(
    """
    Upload the seating arrangement, map key columns, update any reseated students,
    and search by Matric, NUS ID, or Student Name for end-of-exam checks.
    """
)

tab_update, tab_search = st.tabs(
    ["1. Update seat changes", "2. Search for student"]
)

# -----------------------------
# Tab 1: Update seats
# -----------------------------

with tab_update:
    st.subheader("Update seat changes")

    roster = st.session_state.roster

    if roster is None:
        st.warning("Please upload and create a roster first.")
    else:
        search_input = st.text_input(
            "Use this box when a student is reseated, for example because they requested a charging station.",
            placeholder="To find student to update, please enter their Matric Number or Name",
            key="update_search",
        )

        matches = search_roster(roster, search_input)

        if search_input:
            if len(matches) == 0:
                st.error("No matching student found.")
            else:
                st.write("Matching students:")
                st.dataframe(matches, use_container_width=True)

                selected_index = st.selectbox(
                    "Select student",
                    matches.index,
                    format_func=lambda idx: f"{roster.loc[idx, 'student_name']} | {roster.loc[idx, 'matriculation_number']} | current seat: {roster.loc[idx, 'current_seat']}",
                )

                col1, col2 = st.columns(2)

                with col1:
                    new_seat = st.text_input("New/current seat number")

                with col2:
                    reason = st.text_input(
                        "Reason / notes",
                        value="Charging station",
                    )

                if st.button("Update current seat", type="primary"):
                    if not clean_text(new_seat):
                        st.error("Please enter the new/current seat number.")
                    else:
                        st.session_state.roster.loc[selected_index, "current_seat"] = clean_text(new_seat)
                        st.session_state.roster.loc[selected_index, "seat_changed"] = True
                        st.session_state.roster.loc[selected_index, "change_reason"] = clean_text(reason)
                        st.session_state.roster.loc[selected_index, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        st.success("Seat updated.")
                        display_results = format_display(st.session_state.roster)
                        st.dataframe(display_results, use_container_width=True)

                        # Save to disk
                        st.session_state.roster.to_csv(SAVE_PATH, index=False)

        st.markdown("### Current roster")
        display_results = format_display(st.session_state.roster)
        st.dataframe(display_results, use_container_width=True, height=750)

# -----------------------------
# Tab 2: Search
# -----------------------------

with tab_search:
    st.subheader("Search for student during end-of-exam checks")

    roster = st.session_state.roster

    if roster is None:
        st.warning("Please upload and create a roster first.")
    else:
        st.markdown("### Bulk lookup")

        bulk_input = st.text_area(
            "Paste Matric Number or NUS ID, one per line",
            placeholder="A0123456W\nE0001234",
        )

        if st.button("Run bulk lookup"):
            lines = [line.strip() for line in bulk_input.splitlines() if line.strip()]

            output_rows = []

            for item in lines:
                item_matches = search_roster(roster, item)

                if len(item_matches) == 0:
                    output_rows.append({
                        "matriculation_number": "",
                        "student_name": "",
                        "original_seat": "",
                        "current_seat": "",
                        "seat_changed": "",
                        #"change_reason": "",
                    })
                elif len(item_matches) == 1:
                    row = item_matches.iloc[0]
                    output_rows.append({
                        "matriculation_number": row["matriculation_number"],
                        "student_name": row["student_name"],
                        "original_seat": row["original_seat"],
                        "current_seat": row["current_seat"],
                        "seat_changed": row["seat_changed"],
                    })
                else:
                    for _, row in item_matches.iterrows():
                        output_rows.append({
                            "search_input": item,
                            "match_status": "Multiple matches",
                            "matriculation_number": row["matriculation_number"],
                            "student_name": row["student_name"],
                            "original_seat": row["original_seat"],
                            "current_seat": row["current_seat"],
                            "seat_changed": row["seat_changed"],
                        })

            output_df = format_display(output_rows)
            st.dataframe(output_df, use_container_width=True)