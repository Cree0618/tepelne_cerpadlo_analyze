import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import StringIO
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px

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
               
                fig_cop.update_layout(title='COP hodnoty', xaxis_title='Datum', yaxis_title='COP')
                st.plotly_chart(fig_cop, use_container_width=True)

            # Line chart for temperature data and energy consumption
            fig_temp_energy = go.Figure()

            # Calculate the range for inside temperature
            if df['inside_temp_degC'].empty:
                inside_temp_min, inside_temp_max = 0.0, 1.0  # Default values if no data
            else:
                inside_temp_min = float(df['inside_temp_degC'].min())
                inside_temp_max = float(df['inside_temp_degC'].max())

            # Ensure we have a valid range
            if inside_temp_min == inside_temp_max:
                inside_temp_min -= 0.5
                inside_temp_max += 0.5

            # Set the y-axis range for inside temperature, extending 0.5°C below the minimum and 0.5°C above the maximum
            inside_temp_range = [inside_temp_min - 0.5, inside_temp_max + 0.5]

            # Add outside temperature trace
            fig_temp_energy.add_trace(go.Scatter(
                x=df['date'], 
                y=df['outside_temp_degC'], 
                name='Venkovní teplota',
                line=dict(color='blue')
            ))

            # Add inside temperature trace with a secondary y-axis
            fig_temp_energy.add_trace(go.Scatter(
                x=df['date'], 
                y=df['inside_temp_degC'], 
                name='Vnitřní teplota',
                yaxis='y2',
                line=dict(color='red')
            ))

            # Add energy consumption trace with a third y-axis
            fig_temp_energy.add_trace(go.Scatter(
                x=df['date'], 
                y=df['consumed_total_kwh'], 
                name='Spotřebovaná energie',
                yaxis='y3',
                line=dict(color='green')
            ))

            # Update layout with secondary and tertiary y-axes
            fig_temp_energy.update_layout(
                title='Vnitřní a Venkovní teplota vs. Spotřebovaná energie v čase',
                xaxis_title='Datum',
                yaxis=dict(
                    title='Venkovní teplota (°C)',
                    titlefont=dict(color='blue'),
                    tickfont=dict(color='blue')
                ),
                yaxis2=dict(
                    title=None,  # Remove the title
                    titlefont=dict(color='red'),
                    tickfont=dict(color='red'),
                    overlaying='y',
                    side='left',
                    showticklabels=False  # Hide tick labels
                ),
                yaxis3=dict(
                    title='Spotřebovaná energie (kWh)',
                    titlefont=dict(color='green'),
                    tickfont=dict(color='green'),
                    overlaying='y',
                    side='right',
                    anchor='free',
                    position=1.0
                ),
                legend=dict(x=1.1, y=1)
            )

            # Add an annotation for the inside temperature axis
            fig_temp_energy.add_annotation(
                x=0.01,
                y=0.5,
                xref='paper',
                yref='paper',
                text='Vnitřní teplota (°C)',
                textangle=-90,
                showarrow=False,
                font=dict(color='red'),
                xanchor='right',
                yanchor='middle'
            )

            st.plotly_chart(fig_temp_energy, use_container_width=True)

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

            # After the existing graphs, add this new graph
            #st.write("### Vztah mezi vnitřní teplotou, venkovní teplotou a spotřebou energie")

            fig_temp_energy_scatter = go.Figure()

            fig_temp_energy_scatter.add_trace(go.Scatter(
                x=df['inside_temp_degC'],
                y=df['outside_temp_degC'],
                mode='markers',
                marker=dict(
                    size=df['consumed_total_kwh'],
                    sizemode='area',
                    sizeref=2.*max(df['consumed_total_kwh'])/(40.**2),
                    sizemin=4,
                    color=df['consumed_total_kwh'],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(title='Spotřebovaná energie (kWh)')
                ),
                text=df['date'].dt.strftime('%Y-%m-%d %H:%M:%S'),
                hovertemplate='<b>Datum:</b> %{text}<br>' +
                              '<b>Vnitřní teplota:</b> %{x:.1f}°C<br>' +
                              '<b>Venkovní teplota:</b> %{y:.1f}°C<br>' +
                              '<b>Spotřebovaná energie:</b> %{marker.size:.2f} kWh<br>',
            ))

            fig_temp_energy_scatter.update_layout(
                title='Vztah mezi vnitřní teplotou, venkovní teplotou a spotřebou energie',
                xaxis_title='Vnitřní teplota (°C)',
                yaxis_title='Venkovní teplota (°C)',
                height=600,
            )

            st.plotly_chart(fig_temp_energy_scatter, use_container_width=True)

            # After the scatter plot, add this new heatmap
            st.write("### Heatmapa spotřeby energie v závislosti na vnitřní a venkovní teplotě")

            # Create bins for inside and outside temperatures
            df['inside_temp_bin'] = pd.cut(df['inside_temp_degC'], bins=20)
            df['outside_temp_bin'] = pd.cut(df['outside_temp_degC'], bins=20)

            # Group by temperature bins and calculate mean energy consumption
            heatmap_data = df.groupby(['inside_temp_bin', 'outside_temp_bin'])['consumed_total_kwh'].mean().reset_index()

            # Create the heatmap
            fig_heatmap = px.density_heatmap(
                heatmap_data, 
                x='inside_temp_bin', 
                y='outside_temp_bin', 
                z='consumed_total_kwh',
                labels={'inside_temp_bin': 'Vnitřní teplota (°C)', 
                        'outside_temp_bin': 'Venkovní teplota (°C)', 
                        'consumed_total_kwh': 'Průměrná spotřeba energie (kWh)'},
                title='Heatmapa průměrné spotřeby energie v závislosti na vnitřní a venkovní teplotě'
            )

            # Update layout for better readability
            fig_heatmap.update_layout(
                xaxis={'tickangle': 45},
                yaxis={'tickangle': 0},
                height=600,
            )

            st.plotly_chart(fig_heatmap, use_container_width=True)

            # Add explanation
            st.write("""
            Tato heatmapa zobrazuje průměrnou spotřebu energie v závislosti na vnitřní a venkovní teplotě.
            - Barva každé buňky představuje průměrnou spotřebu energie pro danou kombinaci vnitřní a venkovní teploty.
            - Tmavší barvy indikují vyšší spotřebu energie, světlejší barvy nižší spotřebu.

            Hledejte vzory jako:
            - Při jakých kombinacích teplot je spotřeba energie nejvyšší?
            - Jak se mění spotřeba energie s rostoucím rozdílem mezi vnitřní a venkovní teplotou?
            - Existují nějaké neočekávané oblasti s vysokou nebo nízkou spotřebou energie?
            """)
    else:
        st.warning("Prosím vyberte platný rozsah dat.")
else:
    st.write("Prosím nahrajte alespoň jeden CSV soubor.")
