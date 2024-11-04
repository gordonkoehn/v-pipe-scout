import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Streamlit title and description
st.title('Mutation Frequency Over Time')
st.write('This application displays a heatmap of mutation frequencies over time.')

# 1. Data Generation
mutations = [
    "V166A",
    "V166L",
    "N198S",
    "R285C",
    "A376V",
    "A449V",
    "F480L",
    "D484Y",
    "A526V",
    "V557L",
    "G671S",
    "S759A",
    "V792I",
    "E796G",
    "C799F",
    "C799R",
    "E802A",
    "E802D",
    "M924R"
]
start_date = datetime(2024, 4, 23)
end_date = datetime(2024, 10, 7)

# Generate dates three times per week
current_date = start_date
dates = [current_date]
while current_date < end_date:
    current_date += timedelta(days=2)
    dates.append(current_date)
dates.sort()

# Generate random data (skewed towards 0)
data = {}
for mutation in mutations:
    data[mutation] = np.random.choice(np.arange(7), size=len(dates), p=[0.99, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0])

df = pd.DataFrame(data, index=dates)

# 2. Heatmap Construction
fig, ax = plt.subplots(figsize=(12, 8))
im = ax.imshow(df.values.T, cmap='Blues')  # Use a blue colormap

# Set axis labels
ax.set_xticks([0, len(dates) // 2, len(dates) - 1])
ax.set_xticklabels([dates[0].strftime('%Y-%m-%d'), dates[len(dates) // 2].strftime('%Y-%m-%d'), dates[-1].strftime('%Y-%m-%d')], rotation=45)
ax.set_yticks(np.arange(len(mutations)))
ax.set_yticklabels(mutations, fontsize=8)

# Add colorbar
cbar = ax.figure.colorbar(im, ax=ax)
cbar.ax.set_ylabel("Occurrence Frequency", rotation=-90, va="bottom")

plt.tight_layout()

# Display the plot in Streamlit
st.pyplot(fig)