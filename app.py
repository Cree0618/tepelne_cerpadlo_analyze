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
    
    # Date range selector
    st.subheader("Vyberte rozsah dat")
    date_range = st.date_input("Rozsah dat", value=[datetime.now() - timedelta(days=30), datetime.now()])

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
    
    # Filter data based on selected date range
    mask = (df['date'].dt.date >= date_range[0]) & (df['date'].dt.date <= date_range[1])
    df = df.loc[mask]
    
    # Round all numeric columns to 2 decimal places
    numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
    df[numeric_columns] = df[numeric_columns].round(2)
    
    # Display the original dataframe
    st.write("### Původní CSV data")
    st.dataframe(df)
    
    # Define columns to sum and average
    sum_columns = [
        'consumed_total_kwh', 'consumed_heating_kwh', 'consumed_water_kwh', 'consumed_defrost_kwh',
        'generated_total_kwh', 'generated_heating_kwh', 'generated_water_kwh', 'generated_defrost_kwh',
        'heating_hours', 'water_hours', 'defrost_hours', 'bivalence_hours',
        'compressor_starts', 'defrost_starts'
    ]
    avg_columns = ['cop_total', 'cop_heating', 'cop_water', 'outside_temp_degC', 'inside_temp_degC']

    # Ensure all required columns are present
    missing_columns = set(sum_columns + avg_columns) - set(df.columns)
    if missing_columns:
        st.warning(f"Chybějící sloupce v CSV: {', '.join(missing_columns)}")
        st.stop()

    # Calculate sums and averages
    sums = df[sum_columns].sum().round(2)
    
    # Calculate averages, excluding zero values for COP columns
    avgs = pd.Series(index=avg_columns)
    for col in avg_columns:
        if col.startswith('cop_'):
            avgs[col] = df[df[col] > 0][col].mean()
        else:
            avgs[col] = df[col].mean()
    avgs = avgs.round(2)

    # Create a new row with the totals and averages
    new_row = pd.concat([sums, avgs])

    # Append the new row to the original dataframe
    df_with_total = pd.concat([df, pd.DataFrame(new_row).T], ignore_index=True)
    df_with_total.index = df_with_total.index.astype(str)
    df_with_total.index = df_with_total.index[:-1].tolist() + ["Celkem/Průměr"]

    # Display the updated dataframe
    st.write("### Aktualizovaná data s řádkem součtů a průměrů")
    st.dataframe(df_with_total)

    # Create graphs
    st.write("### Grafy")

    # Two columns for graphs
    col1, col2 = st.columns(2)

    with col1:
        # Line chart for energy consumption and generation
        fig_energy = go.Figure()
        fig_energy.add_trace(go.Scatter(x=df['date'], y=df['consumed_total_kwh'], name='Spotřebovaná energie'))
        fig_energy.add_trace(go.Scatter(x=df['date'], y=df['generated_total_kwh'], name='Vyrobená energie'))
        fig_energy.update_layout(title='Spotřeba a výroba energie v čase', xaxis_title='Datum', yaxis_title='Energie (kWh)')
        st.plotly_chart(fig_energy, use_container_width=True)

    with col2:
        # Line chart for COP values
        fig_cop = go.Figure()
        fig_cop.add_trace(go.Scatter(x=df['date'], y=df['cop_total'], name='COP celkem', mode='lines'))
        fig_cop.add_trace(go.Scatter(x=df['date'], y=df['cop_heating'], name='COP topení', mode='lines'))
        fig_cop.add_trace(go.Scatter(x=df['date'], y=df['cop_water'], name='COP voda', mode='lines'))
        fig_cop.update_layout(title='COP hodnoty', xaxis_title='Datum', yaxis_title='COP')
        st.plotly_chart(fig_cop, use_container_width=True)

    # Line chart for temperature data
    fig_temp = go.Figure()

    # Add outside temperature trace
    fig_temp.add_trace(go.Scatter(
        x=df['date'], 
        y=df['outside_temp_degC'], 
        name='Venkovní teplota',
        yaxis='y',
        line=dict(color='blue')
    ))

    # Add inside temperature trace with a secondary y-axis
    fig_temp.add_trace(go.Scatter(
        x=df['date'], 
        y=df['inside_temp_degC'], 
        name='Vnitřní teplota',
        yaxis='y2',
        line=dict(color='red')
    ))

    # Update layout with a secondary y-axis
    fig_temp.update_layout(
        title='Vnitřní a Venkovní teplota v čase',
        xaxis_title='Datum',
        yaxis_title='Venkovní teplota (°C)',
        yaxis2=dict(
            title='Vnitřní teplota (°C)',
            overlaying='y',
            side='right',
            range=[df['inside_temp_degC'].min() - 4, df['inside_temp_degC'].max() + 1]
        ),
        legend=dict(x=1.1, y=1)
    )
    st.plotly_chart(fig_temp, use_container_width=True)

    # Key Performance Indicators (KPIs)
    st.write("### Klíčové ukazatele výkonu (KPI)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Průměrný COP", f"{avgs['cop_total']:.2f}")
    col2.metric("Celková spotřeba energie", f"{sums['consumed_total_kwh']:.2f} kWh")
    col3.metric("Celková vyrobená energie", f"{sums['generated_total_kwh']:.2f} kWh")
    col4.metric("Počet startů kompresoru", f"{sums['compressor_starts']:.0f}")

    # Energy efficiency calculation
    energy_efficiency = (sums['generated_total_kwh'] / sums['consumed_total_kwh']) * 100 if sums['consumed_total_kwh'] > 0 else 0
    st.write(f"### Energetická účinnost: {energy_efficiency:.2f}%")

    # Convert the updated dataframe to CSV
    csv_buffer = StringIO()
    df_with_total.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    # Download button for the updated CSV file
    st.download_button(
        label="Stáhnout aktualizovaný CSV soubor",
        data=csv_data,
        file_name="aktualizovana_data.csv",
        mime="text/csv"
    )
else:
    st.write("Prosím nahrajte alespoň jeden CSV soubor.")
