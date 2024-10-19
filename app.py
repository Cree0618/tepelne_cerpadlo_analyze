import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import StringIO
import numpy as np
from datetime import datetime, timedelta

# Set page config
st.set_page_config(page_title="Analýza dat tepelného čerpadla", layout="wide")

# Title of the Streamlit app
st.title("Zpracování CSV dat z tepelného čerpadla")

# Sidebar for file upload and date range selection
with st.sidebar:
    st.header("Nastavení")
    uploaded_file1 = st.file_uploader("Nahraj první CSV soubor", type=["csv"], key="file1")
    uploaded_file2 = st.file_uploader("Nahraj druhý CSV soubor (volitelné)", type=["csv"], key="file2")

def process_csv(file):
    if file is not None:
        try:
            df = pd.read_csv(file)
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            return df
        except Exception as e:
            st.error(f"Chyba při načítání souboru: {str(e)}")
            return None
    return None

df1 = process_csv(uploaded_file1)
df2 = process_csv(uploaded_file2)

if df1 is not None:
    if df2 is not None:
        df = pd.concat([df1, df2], ignore_index=True)
        df = df.drop_duplicates(subset=['date'], keep='first')
        df = df.sort_values('date')
    else:
        df = df1
    
    # Get the min and max dates from the dataframe
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()
    
    # Update the date range selector with the dataframe's date range
    st.sidebar.subheader("Vyberte rozsah dat")
    date_range = st.sidebar.date_input(
        "Rozsah dat",
        value=[min_date, max_date],
        min_value=min_date,
        max_value=max_date
    )
    
    # Check if date_range is a tuple with two dates
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        # Ensure the selected date range is within the dataframe's date range
        start_date = max(start_date, min_date)
        end_date = min(end_date, max_date)
        
        # Filter data based on selected date range
        mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
        df_filtered = df.loc[mask]
        
        if df_filtered.empty:
            st.warning("Žádná data nejsou k dispozici pro vybraný rozsah dat.")
        else:
            # Use the filtered dataframe for further processing
            df = df_filtered
            
            # Continue with the rest of your data processing and visualization code here
            # For example:
            st.write("### Původní CSV data")
            st.dataframe(df)
            
            # Add your graphs and other analysis here
            # ...

    else:
        st.warning("Prosím vyberte platný rozsah dat.")

else:
    st.write("Prosím nahrajte alespoň jeden CSV soubor.")

# Remove any code that tries to access 'df' outside of the above if-else blocks
