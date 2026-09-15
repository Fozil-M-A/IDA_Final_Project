# IDA_Final_Project

A **Streamlit-based Executive Quality Dashboard** for analyzing automotive component defect rates, supplier market share, and transmission penetration metrics.

## Overview

This project implements an interactive data analysis application that answers key business questions about automotive component quality and supplier performance:

1. **Market Share Analysis**: What is the market share of manufacturer 205 parts vs. competitors?
2. **Penetration Metrics**: In every xth gearbox, there are parts from 205 (advertising metric).
3. **Quality Comparison**: How does the defect frequency of manufacturer 205 parts compare to competitors?
4. **Defect Propagation**: How does part-level defect data translate to gearbox-level reliability?

## Features

### 📊 Interactive Visualizations
- **Defect Rate Analysis**: Volume-weighted defect rates by part type and manufacturer
- **Market Share Charts**: Supplier market share distribution
- **Relative Defect Index**: Manufacturer 205 quality performance vs. competition
- **Trend Analysis**: Defect rate trends over model years
- **Defect Propagation Logic**: Gearbox-level reliability modeling

### 🔍 Interactive Filters
- **Analysis Period**: Customize production year range
- **Vehicle Type**: Filter by vehicle category
- **Gearbox Family**: Select specific transmission families
- **Part Type**: Focus on specific components
- **Part Manufacturer**: Compare specific suppliers

### 📈 Data Explorer
- Full dataset browsing with search capability
- CSV export functionality
- Row-level data inspection

## Technical Stack

- **Python 3.12+**
- **Streamlit**: Interactive web framework
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations
- **Plotly**: Interactive visualizations
- **JupyterLab**: Notebook environment (for development)

## Installation

### Via Conda (Recommended)

```bash
conda env create -f environment.yml
conda activate ida-final
streamlit run SoSe26_Case_Study_App_Group_1.py
```

### Via pip

```bash
pip install -r requirements.txt
streamlit run SoSe26_Case_Study_App_Group_1.py
```

## Project Structure

```
IDA_Final_Project/
├── SoSe26_Case_Study_App_Group_1.py    # Main Streamlit application
├── SoSe26_Case_Study_finalData_Group_01.csv  # Processed dataset
├── SoSe26_Case_Study_Group_01.ipynb    # Jupyter analysis notebook
├── SoSe26_Case_Study_Group_01.html     # HTML export of notebook
├── environment.yml                      # Conda environment specification
├── www/
│   └── data-analytics-logo.jpg          # Dashboard logo
├── README.md                            # This file
└── LICENSE                              # MIT License
```

## Data Format

The dataset (`SoSe26_Case_Study_finalData_Group_01.csv`) is pre-aggregated with two record types:

### Part Summary Records
- **vehicle_year**: Production model year
- **vehicle_type**: Vehicle category
- **gearbox_family**: Transmission family
- **part_type**: Component type
- **part_manufacturer**: Supplier ID (e.g., 205, 206, 207, 208)
- **installed_parts**: Volume of parts installed
- **defective_parts**: Count of defective parts
- **market_share**: Pre-computed market share %
- **defect_frequency**: Pre-computed defect rate %

### Gearbox Summary Records
- **vehicle_year, vehicle_type, gearbox_family**: Identification
- **gearboxes_total**: Total gearboxes produced
- **gearboxes_with_205**: Gearboxes containing parts from manufacturer 205
- **every_xth_gearbox**: Pre-computed penetration metric

## Key Calculations

### Volume-Weighted Defect Rate
```
defect_rate = sum(defective_parts) / sum(installed_parts)
```
✅ Correctly aggregated across groups, never an average of pre-computed ratios.

### Market Share (205-Scoped)
```
market_share = sum(205_installed_parts) / sum(installed_parts in part types 205 supplies)
```
Restricts comparison to part types manufacturer 205 actually competes in.

### Relative Defect Index
```
index = (205_defect_rate / competitor_defect_rate) × 100
```
- **100** = exactly on par with competition
- **< 100** = fewer defects (better)
- **> 100** = more defects (worse)

### Gearbox-Level Defect Probability
```
P(gearbox defective) = 1 − ∏(1 − defect_rate_i) for each part type i
```
Models defect propagation assuming independence across constituent part types.

## Usage

1. **Run the app**:
   ```bash
   streamlit run SoSe26_Case_Study_App_Group_1.py
   ```

2. **Use the sidebar filters** to customize your analysis:
   - Select analysis period (production years)
   - Choose vehicle types, gearbox families, part types, manufacturers

3. **Navigate tabs**:
   - **📈 Executive KPI Overview**: High-level metrics and competitive analysis
   - **📉 Defect Trends**: Defect rate trends over time
   - **🧩 Defect Propagation**: Gearbox-level reliability modeling
   - **🔎 Data Explorer**: Browse and export raw data

## Notes on Data Aggregation

⚠️ **Critical**: This dataset is **pre-aggregated** (sums per group, not per-unit records). Ratio columns must **never** be averaged directly:

❌ **Wrong**: Average the `market_share` column across part types  
✅ **Right**: Re-aggregate from `installed_parts` and `defective_parts` columns  

This ensures volume-weighted figures that match real-world supplier performance.

## Case Study Context

This application was developed for **Case Study 205** analyzing automotive transmission component quality and supplier performance. It demonstrates:
- Correct handling of pre-aggregated financial/operational data
- Volume-weighted analytical calculations
- Interactive business intelligence dashboards
- Professional data visualization with Plotly

## License

MIT License – See [LICENSE](LICENSE) file for details.

## Authors

**Group 1** – IDA Final Project (SoSe 2026)

---

For questions or contributions, please open an issue or submit a pull request.
