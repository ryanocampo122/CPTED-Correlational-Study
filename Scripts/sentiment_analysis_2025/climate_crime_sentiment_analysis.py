"""
Climate Variability, Urban Crime, and Public Safety Perception
Prairie Cities Analysis Pipeline  —  2009–2025
Centre for Forensic Behavioural Science and Justice Studies

INPUTS  (place in same directory or adjust paths below)
-------
Reddit sentiment files (era-banded):
    reddit_2009_2013_for_gis.csv
    reddit_2014_2019_for_gis.csv
    reddit_2020_2021_for_gis.csv
    reddit_2022_2023_for_gis.csv
    reddit_2024_2025_for_gis.csv

Climate files (ECCC, imputed):
    Master_All_Cities_Daily_Climate_2010_to_2025_imputed.csv

Crime files (Statistics Canada UCR, Table 35-10-0177-01):
    Actual_Incidents_Edmonton.csv
    Actual_Incidents_incidents_Saskatoon.csv
    Actual_Incidents_Regina.csv
    Actual_Incidents_Winnipeg.csv

OUTPUTS
-------
Intermediate CSVs:
    reddit_monthly.csv
    climate_monthly.csv
    merged_reddit_climate.csv
    crime_categorized.csv
    crime_total.csv
    volatility_table.csv
    climate_sentiment_correlations.csv
    climate_crime_correlations.csv
    seasonal_sentiment_stats.csv

Figures (PNG, 150 dpi):
    fig01_sentiment_trajectory.png
    fig02_volatility_bars.png
    fig03_rolling_volatility.png
    fig04_volatility_heatmap.png
    fig05_temp_anomaly_sentiment.png
    fig06_heat_sentiment.png
    fig07_humidity_sentiment.png
    fig08_crime_composition.png
    fig09_crime_era_composition.png
    fig10_temp_crime.png
    fig11_heatdays_crime.png
    fig12_humidity_crime.png
    fig13_spatial_map.png
    fig14_spatial_overlay.png
    fig15_seasonal_sentiment.png
    fig16_corr_heatmaps.png

DEPENDENCIES: 
    pip install pandas numpy matplotlib scipy statsmodels
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats
from statsmodels.tsa.stattools import adfuller

warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = './data'        # folder containing all input CSVs
OUTPUT_DIR = './outputs'     # folder for figures and intermediate CSVs
os.makedirs(OUTPUT_DIR, exist_ok=True)

def inp(filename):
    return os.path.join(DATA_DIR, filename)

def out(filename):
    return os.path.join(OUTPUT_DIR, filename)

# ── Global style ──────────────────────────────────────────────────────────────
FONT = 'Liberation Serif'
plt.rcParams['font.family'] = FONT
plt.rcParams['font.size']   = 9

CITIES = ['Edmonton', 'Saskatoon', 'Regina', 'Winnipeg']

CITY_STYLES = {
    'Edmonton':  {'color': 'black',   'ls': '-',  'marker': 'o', 'hatch': ''},
    'Saskatoon': {'color': '#444444', 'ls': '--', 'marker': 's', 'hatch': '///'},
    'Regina':    {'color': '#777777', 'ls': '-.', 'marker': '^', 'hatch': '...'},
    'Winnipeg':  {'color': '#AAAAAA', 'ls': ':',  'marker': 'D', 'hatch': 'xxx'},
}

CITY_COORDS = {
    'Edmonton':  (53.546, -113.494),
    'Saskatoon': (52.133, -106.670),
    'Regina':    (50.445, -104.619),
    'Winnipeg':  (49.895,  -97.138),
}

ERA_ORDER = [
    'Pre-Phase (2009-2013)',
    'Growth Phase (2014-2019)',
    'Pandemic Phase (2020-2021)',
    'Post-Pandemic (2022-2023)',
    'Recent (2024-2025)',
]
ERA_SHORT = ['Pre-Phase', 'Growth', 'Pandemic', 'Post-\nPandemic', 'Recent']

ERA_STARTS = [
    pd.Timestamp('2009-01-01'), pd.Timestamp('2014-01-01'),
    pd.Timestamp('2020-01-01'), pd.Timestamp('2022-01-01'),
    pd.Timestamp('2024-01-01'), pd.Timestamp('2026-01-01'),
]
ERA_GRAYS = ['0.97', '0.90', '0.97', '0.90', '0.97']

CAT_ORDER = ['Violent', 'Property', 'Drug', 'Traffic', 'Other']
CAT_GRAYS = {
    'Violent': '0.10', 'Property': '0.35', 'Drug': '0.60',
    'Traffic': '0.75', 'Other':    '0.90',
}

PROVINCE_OUTLINES = [
    [(49.0, -120.0), (60.0, -120.0), (60.0, -110.0), (49.0, -110.0), (49.0, -120.0)],
    [(49.0, -110.0), (60.0, -110.0), (60.0, -101.3), (49.0, -101.3), (49.0, -110.0)],
    [(49.0, -101.3), (60.0, -101.3), (60.0,  -95.0), (49.0,  -95.0), (49.0, -101.3)],
]


# =============================================================================
# SECTION 1  —  ERA ASSIGNMENT
# =============================================================================
def assign_era(year):
    if year <= 2013:
        return 'Pre-Phase (2009-2013)'
    elif year <= 2019:
        return 'Growth Phase (2014-2019)'
    elif year <= 2021:
        return 'Pandemic Phase (2020-2021)'
    elif year <= 2023:
        return 'Post-Pandemic (2022-2023)'
    else:
        return 'Recent (2024-2025)'


# =============================================================================
# SECTION 2  —  LOAD AND AGGREGATE REDDIT SENTIMENT
# =============================================================================
def load_reddit():
    """
    Combine five era-banded Reddit GIS files into one monthly sentiment table.
    The 2009-2013 file is pre-aggregated at monthly level; the remaining four
    are post-level and are aggregated here.
    """
    print("Loading Reddit sentiment data...")

    # 2009-2013: already monthly
    df1 = pd.read_csv(inp('reddit_2009_2013_for_gis.csv'))
    df1 = df1.rename(columns={
        'subreddit': 'city',
        'mean_sentiment_compound': 'mean_sentiment'
    })
    df1['year_month'] = pd.to_datetime(df1[['year', 'month']].assign(day=1))
    df1['era']        = df1['year'].apply(assign_era)
    df1 = df1[['city', 'year', 'month', 'year_month', 'era',
               'n_posts', 'mean_sentiment',
               'pct_negative', 'pct_positive', 'pct_neutral']].copy()

    monthly_parts = [df1]

    # 2014-2025: post-level — aggregate to monthly
    for period in ['2014_2019', '2020_2021', '2022_2023', '2024_2025']:
        df = pd.read_csv(inp(f'reddit_{period}_for_gis.csv'))
        df = df.rename(columns={'subreddit': 'city'})
        df['year_month'] = pd.to_datetime(df[['year', 'month']].assign(day=1))
        df['era']        = df['year'].apply(assign_era)

        agg = df.groupby(['city', 'year', 'month', 'year_month', 'era']).agg(
            n_posts       = ('sentiment_compound', 'count'),
            mean_sentiment= ('sentiment_compound', 'mean'),
            pct_negative  = ('sentiment_category', lambda x: (x == 'negative').mean() * 100),
            pct_positive  = ('sentiment_category', lambda x: (x == 'positive').mean() * 100),
            pct_neutral   = ('sentiment_category', lambda x: (x == 'neutral').mean() * 100),
        ).reset_index()
        monthly_parts.append(agg)

    reddit = (pd.concat(monthly_parts, ignore_index=True)
                .sort_values(['city', 'year_month'])
                .reset_index(drop=True))

    reddit.to_csv(out('reddit_monthly.csv'), index=False)
    print(f"  Reddit monthly: {reddit.shape[0]} rows, "
          f"{reddit['year_month'].min().date()} → {reddit['year_month'].max().date()}")
    return reddit


# =============================================================================
# SECTION 3  —  LOAD AND AGGREGATE CLIMATE DATA
# =============================================================================
def load_climate():
    """
    Read master daily climate file, derive monthly aggregates, and compute
    temperature anomalies relative to each city's long-run monthly mean.
    """
    print("Loading climate data...")

    daily = pd.read_csv(
        inp('Master_All_Cities_Daily_Climate_2010_to_2025_imputed.csv'),
        parse_dates=['Date']
    )
    daily.rename(columns={'City': 'city'}, inplace=True)
    daily['temp_mean']  = (daily['Temperature_C_max'] + daily['Temperature_C_min']) / 2
    daily['year_month'] = daily['Date'].dt.to_period('M').dt.to_timestamp()

    monthly = daily.groupby(['city', 'year_month']).agg(
        temp_mean   = ('temp_mean',                 'mean'),
        temp_max    = ('Temperature_C_max',         'mean'),
        temp_min    = ('Temperature_C_min',         'mean'),
        humidity    = ('Relative_Humidity_Pct_mean','mean'),
        snow_ground = ('Snow_On_Ground_cm_mean',    'mean'),
        wind_chill  = ('Wind_Chill_mean',           'mean'),
        heat_days   = ('temp_mean', lambda x: (x > 27).sum()),   # days > 27 °C
        cold_days   = ('temp_mean', lambda x: (x < -20).sum()),  # days < -20 °C
    ).reset_index()

    # Temperature anomaly relative to city × month long-run mean
    monthly['month_num']  = monthly['year_month'].dt.month
    norms = (monthly
             .groupby(['city', 'month_num'])['temp_mean']
             .mean()
             .reset_index()
             .rename(columns={'temp_mean': 'temp_norm'}))
    monthly = monthly.merge(norms, on=['city', 'month_num'])
    monthly['temp_anomaly'] = monthly['temp_mean'] - monthly['temp_norm']

    monthly.to_csv(out('climate_monthly.csv'), index=False)
    print(f"  Climate monthly: {monthly.shape[0]} rows")
    return monthly


# =============================================================================
# SECTION 4  —  LOAD CRIME DATA
# =============================================================================
def load_crime():
    """
    Read four city UCR files, concatenate, classify violations into five broad
    categories, and save categorized and total-crime tables.
    """
    print("Loading crime data...")

    file_map = [
        ('Edmonton',            'Edmonton'),
        ('incidents_Saskatoon', 'Saskatoon'),
        ('Regina',              'Regina'),
        ('Winnipeg',            'Winnipeg'),
    ]
    parts = []
    for file_suffix, city_name in file_map:
        df = pd.read_csv(inp(f'Actual_Incidents_{file_suffix}.csv'))
        df['city'] = city_name
        parts.append(df)

    crime = pd.concat(parts, ignore_index=True)
    crime.rename(columns={'REF_DATE': 'year', 'VALUE': 'incidents',
                          'Violations': 'violation'}, inplace=True)
    crime = crime[['city', 'year', 'violation', 'incidents']].dropna(subset=['incidents'])

    def categorize(v):
        v = v.lower()
        if 'total' in v:
            return 'Total'
        if any(x in v for x in ['assault', 'homicide', 'robbery', 'sexual',
                                  'uttering threats', 'forcible', 'weapons', 'firearms']):
            return 'Violent'
        if any(x in v for x in ['theft', 'break', 'enter', 'fraud',
                                  'mischief', 'arson', 'property']):
            return 'Property'
        if any(x in v for x in ['drug', 'cannabis', 'heroin', 'cocaine',
                                  'methamphetamine', 'controlled']):
            return 'Drug'
        if any(x in v for x in ['traffic', 'impaired', 'driving', 'motor vehicle']):
            return 'Traffic'
        return 'Other'

    crime['category'] = crime['violation'].apply(categorize)
    crime['era']      = crime['year'].apply(assign_era)

    crime_cat   = (crime[crime['category'] != 'Total']
                   .groupby(['city', 'year', 'era', 'category'])['incidents']
                   .sum().reset_index())
    crime_total = crime[crime['category'] == 'Total'].copy()

    crime_cat.to_csv(out('crime_categorized.csv'), index=False)
    crime_total.to_csv(out('crime_total.csv'), index=False)
    print(f"  Crime categorized: {crime_cat.shape[0]} rows")
    return crime_cat, crime_total


# =============================================================================
# SECTION 5  —  MERGE AND COMPUTE CORRELATIONS
# =============================================================================
def build_merged_and_correlations(reddit, climate):
    """Merge monthly Reddit + climate; compute climate–sentiment correlations."""
    print("Merging and computing correlations...")

    merged = reddit.merge(climate, on=['city', 'year_month'], how='inner')
    merged.to_csv(out('merged_reddit_climate.csv'), index=False)
    print(f"  Merged: {merged.shape[0]} rows")

    clim_vars = ['temp_mean', 'temp_anomaly', 'humidity',
                 'snow_ground', 'heat_days', 'cold_days']
    records = []
    for city in CITIES:
        sub = merged[merged['city'] == city].dropna(subset=['mean_sentiment'])
        for var in clim_vars:
            s = sub[[var, 'mean_sentiment']].dropna()
            if len(s) < 10:
                continue
            r, p   = stats.pearsonr(s[var], s['mean_sentiment'])
            rs, ps = stats.spearmanr(s[var], s['mean_sentiment'])
            records.append({
                'City': city, 'Variable': var,
                'Pearson_r': round(r, 3),  'Pearson_p': round(p, 4),
                'Spearman_r': round(rs, 3), 'Spearman_p': round(ps, 4),
                'N': len(s),
                'Sig': ('***' if p < 0.001 else '**' if p < 0.01
                        else '*' if p < 0.05 else ''),
            })

    corr_df = pd.DataFrame(records)
    corr_df.to_csv(out('climate_sentiment_correlations.csv'), index=False)
    return merged, corr_df


def compute_crime_climate_correlations(crime_cat, climate):
    """Annual violent crime × annual climate correlations."""
    climate_cp = climate.copy()
    climate_cp['year'] = climate_cp['year_month'].dt.year
    clim_annual = (climate_cp
                   .groupby(['city', 'year'])
                   .agg(temp_mean   = ('temp_mean',   'mean'),
                        temp_anomaly= ('temp_anomaly','mean'),
                        humidity    = ('humidity',    'mean'),
                        heat_days   = ('heat_days',   'sum'),
                        cold_days   = ('cold_days',   'sum'))
                   .reset_index())

    violent = (crime_cat[crime_cat['category'] == 'Violent']
               .groupby(['city', 'year'])['incidents']
               .sum().reset_index()
               .rename(columns={'incidents': 'violent_incidents'}))

    df = violent.merge(clim_annual, on=['city', 'year'])

    records = []
    for city in CITIES:
        sub = df[df['city'] == city].dropna()
        for var in ['temp_mean', 'temp_anomaly', 'humidity', 'heat_days', 'cold_days']:
            s = sub[[var, 'violent_incidents']].dropna()
            if len(s) < 5:
                continue
            r, p   = stats.pearsonr(s[var], s['violent_incidents'])
            rs, ps = stats.spearmanr(s[var], s['violent_incidents'])
            records.append({
                'City': city, 'Variable': var,
                'Pearson_r': round(r, 3),  'Pearson_p': round(p, 4),
                'Spearman_r': round(rs, 3), 'Spearman_p': round(ps, 4),
                'N': len(s),
                'Sig': ('***' if p < 0.001 else '**' if p < 0.01
                        else '*' if p < 0.05 else ''),
            })

    clim_crime_df = pd.DataFrame(records)
    clim_crime_df.to_csv(out('climate_crime_correlations.csv'), index=False)
    return df, clim_crime_df


# =============================================================================
# SECTION 6  —  VOLATILITY TABLE
# =============================================================================
def compute_volatility(reddit):
    print("Computing volatility statistics...")
    records = []
    for city in CITIES:
        sub_city = reddit[reddit['city'] == city].sort_values('year_month')
        for era in ERA_ORDER:
            sub = sub_city[sub_city['era'] == era]['mean_sentiment'].dropna()
            if len(sub) < 3:
                continue
            city_mean = sub_city['mean_sentiment'].mean()
            city_std  = sub_city['mean_sentiment'].std()
            z = (sub - city_mean) / city_std if city_std > 0 else sub * 0
            adf_stat, adf_p = (adfuller(sub, autolag='AIC')[:2]
                               if len(sub) >= 10 else (np.nan, np.nan))
            records.append({
                'City': city, 'Era': era,
                'N_months': len(sub),
                'Mean':     round(sub.mean(), 4),
                'Std_Dev':  round(sub.std(),  4),
                'CV': round(sub.std() / abs(sub.mean()), 4)
                      if abs(sub.mean()) > 0.001 else np.nan,
                'Min':   round(sub.min(), 4),
                'Max':   round(sub.max(), 4),
                'Range': round(sub.max() - sub.min(), 4),
                'ADF_stat': round(adf_stat, 3) if not np.isnan(adf_stat) else 'N/A',
                'ADF_p':    round(adf_p,    3) if not np.isnan(adf_p)    else 'N/A',
                'Mean_Z':   round(z.mean(), 4),
            })
    vol_df = pd.DataFrame(records)
    vol_df.to_csv(out('volatility_table.csv'), index=False)
    return vol_df


# =============================================================================
# SECTION 7  —  HELPER: ERA BANDS ON AX
# =============================================================================
def add_era_bands(ax, label_y_frac=0.97, fontsize=7):
    for i in range(5):
        ax.axvspan(ERA_STARTS[i], ERA_STARTS[i + 1], alpha=1,
                   color=ERA_GRAYS[i], zorder=0)
        mid = ERA_STARTS[i] + (ERA_STARTS[i + 1] - ERA_STARTS[i]) / 2
        ymin, ymax = ax.get_ylim()
        ax.text(mid, ymin + (ymax - ymin) * label_y_frac,
                ERA_SHORT[i].split('\n')[0],
                ha='center', va='top', fontsize=fontsize,
                color='#444444', style='italic')


def add_province_outlines(ax):
    for poly in PROVINCE_OUTLINES:
        xs = [p[1] for p in poly]
        ys = [p[0] for p in poly]
        ax.plot(xs, ys, color='black', lw=0.8, alpha=0.5)


# =============================================================================
# SECTION 8  —  FIGURES 1–4  (Sentiment trajectory and volatility)
# =============================================================================
def fig01_sentiment_trajectory(reddit):
    print("  Fig 1: Sentiment trajectory")
    fig, ax = plt.subplots(figsize=(13, 4.5))
    for i in range(5):
        ax.axvspan(ERA_STARTS[i], ERA_STARTS[i + 1],
                   alpha=1, color=ERA_GRAYS[i], zorder=0)

    for city in CITIES:
        s   = CITY_STYLES[city]
        sub = (reddit[reddit['city'] == city]
               .sort_values('year_month')
               .set_index('year_month')['mean_sentiment']
               .resample('MS').mean()
               .rolling(3, min_periods=1).mean())
        ax.plot(sub.index, sub.values,
                color=s['color'], ls=s['ls'], lw=1.5, label=city)

    ax.axhline(0, color='black', lw=0.8, ls='--', alpha=0.6)
    ax.set_xlim(ERA_STARTS[0], ERA_STARTS[-1])
    ax.set_ylabel('Mean Sentiment Score (3-mo. Rolling)', fontsize=10)
    ax.set_xlabel('Date', fontsize=10)
    ax.set_title('Figure 1. Monthly Sentiment Score Trajectory by City and Era (2009–2025)',
                 fontsize=11, fontweight='bold')
    ax.legend(loc='lower right', fontsize=8)

    ymax = ax.get_ylim()[1]
    for i in range(5):
        mid = ERA_STARTS[i] + (ERA_STARTS[i + 1] - ERA_STARTS[i]) / 2
        ax.text(mid, ymax * 0.97, ERA_SHORT[i].split('\n')[0],
                ha='center', va='top', fontsize=7, color='#444444', style='italic')

    for sp in ax.spines.values():
        sp.set_edgecolor('black')
    plt.tight_layout()
    plt.savefig(out('fig01_sentiment_trajectory.png'), dpi=150, bbox_inches='tight')
    plt.close()


def fig02_volatility_bars(vol_df):
    print("  Fig 2: Volatility bar chart")
    fig, ax = plt.subplots(figsize=(12, 4.5))
    x = np.arange(len(ERA_ORDER))
    w = 0.18
    for i, city in enumerate(CITIES):
        s = CITY_STYLES[city]
        vals = []
        for era in ERA_ORDER:
            row = vol_df[(vol_df['City'] == city) & (vol_df['Era'] == era)]
            vals.append(row['Std_Dev'].values[0] if len(row) > 0 else 0)
        ax.bar(x + i * w, vals, w, label=city,
               color=s['color'], hatch=s['hatch'],
               edgecolor='white', linewidth=0.5)

    ax.set_xticks(x + 1.5 * w)
    ax.set_xticklabels(ERA_SHORT, fontsize=9)
    ax.set_ylabel('Sentiment Standard Deviation', fontsize=10)
    ax.set_title('Figure 2. Sentiment Volatility (Std. Deviation) by City and Era',
                 fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor('black')
    plt.tight_layout()
    plt.savefig(out('fig02_volatility_bars.png'), dpi=150, bbox_inches='tight')
    plt.close()


def fig03_rolling_volatility(reddit):
    """
    12-month rolling standard deviation per city (2009–2025).
    Missing monthly observations (13–15% per city) are imputed using seasonal
    decomposition prior to computing the rolling window.  Imputed windows are
    shaded red in each panel.
    """
    print("  Fig 3: Rolling volatility (with imputation shading)")
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), sharey=True)

    for ax, city in zip(axes.flatten(), CITIES):
        sub = (reddit[reddit['city'] == city]
               .sort_values('year_month')
               .set_index('year_month')['mean_sentiment']
               .resample('MS').mean())

        # ── Seasonal-decomposition imputation ──────────────────────────────
        observed_mask = sub.notna()
        month_means   = sub.groupby(sub.index.month).mean()

        imputed = sub.copy()
        for idx in sub[~observed_mask].index:
            seasonal_val = month_means[idx.month]
            imputed[idx] = seasonal_val  # first-pass seasonal fill

        # Linear interpolation over deseasonalised residual
        deseason = imputed - imputed.index.map(lambda d: month_means[d.month])
        deseason = deseason.interpolate(method='linear')
        imputed  = deseason + imputed.index.map(lambda d: month_means[d.month])

        # Mark imputed windows for red shading
        imputed_windows = ~observed_mask

        rolled_std = imputed.rolling(12, min_periods=6).std()

        # Era bands
        for i in range(5):
            ax.axvspan(ERA_STARTS[i], ERA_STARTS[i + 1],
                       alpha=1, color=ERA_GRAYS[i], zorder=0)

        # Red shading over imputed regions
        for idx in imputed.index[imputed_windows]:
            ax.axvspan(idx, idx + pd.DateOffset(months=1),
                       alpha=0.35, color='red', zorder=1, lw=0)

        ax.plot(rolled_std.index, rolled_std.values, color='black', lw=1.5, zorder=2)
        ax.fill_between(rolled_std.index, 0, rolled_std.values,
                        alpha=0.15, color='black', zorder=2)
        ax.set_title(city, fontsize=10, fontweight='bold')
        ax.set_xlabel('Date', fontsize=8)
        ax.set_ylabel('Rolling Std Dev (12-mo.)', fontsize=8)
        ax.set_xlim(ERA_STARTS[0], ERA_STARTS[-1])
        for sp in ax.spines.values():
            sp.set_edgecolor('black')

    red_patch = mpatches.Patch(color='red', alpha=0.4, label='Imputed window')
    fig.legend(handles=[red_patch], loc='lower right', fontsize=8)
    fig.suptitle('Figure 3. 12-Month Rolling Sentiment Volatility by City (2009–2025)',
                 fontsize=11, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(out('fig03_rolling_volatility.png'), dpi=150, bbox_inches='tight')
    plt.close()


def fig04_volatility_heatmap(vol_df):
    print("  Fig 4: Volatility heatmap")
    fig, ax = plt.subplots(figsize=(10, 4))
    pivot   = vol_df.pivot(index='City', columns='Era', values='Std_Dev')[ERA_ORDER]

    im = ax.imshow(pivot.values, cmap='Greys', aspect='auto', vmin=0, vmax=0.6)
    ax.set_xticks(range(len(ERA_ORDER)))
    ax.set_xticklabels(ERA_SHORT, fontsize=8)
    ax.set_yticks(range(len(CITIES)))
    ax.set_yticklabels(CITIES, fontsize=9)

    for i in range(len(CITIES)):
        for j in range(len(ERA_ORDER)):
            val   = pivot.values[i, j]
            color = 'white' if val > 0.35 else 'black'
            ax.text(j, i, f'{val:.3f}', ha='center', va='center',
                    fontsize=9, color=color)

    plt.colorbar(im, ax=ax, label='Std. Deviation', shrink=0.8)
    ax.set_title('Figure 4. Sentiment Volatility Heatmap (Std. Deviation by City and Era)',
                 fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out('fig04_volatility_heatmap.png'), dpi=150, bbox_inches='tight')
    plt.close()


# =============================================================================
# SECTION 9  —  FIGURES 5–7  (Climate × Sentiment scatters)
# =============================================================================
def _scatter_grid(merged, x_var, x_label, y_var, y_label, title, outname):
    fig, axes = plt.subplots(1, 4, figsize=(14, 4), sharey=True)
    for ax, city in zip(axes, CITIES):
        s   = CITY_STYLES[city]
        sub = merged[merged['city'] == city].dropna(subset=[x_var, y_var])
        ax.scatter(sub[x_var], sub[y_var],
                   color=s['color'], marker=s['marker'], s=20, alpha=0.5)
        if sub[x_var].std() > 0 and len(sub) > 3:
            m, b, r, p, _ = stats.linregress(sub[x_var], sub[y_var])
            xr = np.linspace(sub[x_var].min(), sub[x_var].max(), 100)
            ax.plot(xr, m * xr + b, color='black', lw=1.5)
            star = ('***' if p < 0.001 else '**' if p < 0.01
                    else '*' if p < 0.05 else '')
            ax.set_title(f'{city}\nr={r:.2f}{star}', fontsize=9, fontweight='bold')
        else:
            ax.set_title(city, fontsize=9, fontweight='bold')
        ax.set_xlabel(x_label, fontsize=8)
        ax.axhline(0, color='gray', lw=0.7, ls='--')
        for sp in ax.spines.values():
            sp.set_edgecolor('black')
    axes[0].set_ylabel(y_label, fontsize=9)
    fig.suptitle(title, fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out(outname), dpi=150, bbox_inches='tight')
    plt.close()


def fig05_temp_anomaly_sentiment(merged):
    print("  Fig 5: Temp anomaly vs sentiment")
    _scatter_grid(merged, 'temp_anomaly', 'Temp. Anomaly (°C)',
                  'mean_sentiment', 'Mean Sentiment Score',
                  'Figure 5. Temperature Anomaly vs. Sentiment Score by City',
                  'fig05_temp_anomaly_sentiment.png')


def fig06_heat_sentiment(merged):
    print("  Fig 6: Heat days vs sentiment")
    _scatter_grid(merged, 'heat_days', 'Heat Days (>27°C) per Month',
                  'mean_sentiment', 'Mean Sentiment Score',
                  'Figure 6. Monthly Heat Days (>27°C) vs. Sentiment Score by City',
                  'fig06_heat_sentiment.png')


def fig07_humidity_sentiment(merged):
    print("  Fig 7: Humidity vs sentiment")
    _scatter_grid(merged, 'humidity', 'Relative Humidity (%)',
                  'mean_sentiment', 'Mean Sentiment Score',
                  'Figure 7. Relative Humidity vs. Sentiment Score by City',
                  'fig07_humidity_sentiment.png')


# =============================================================================
# SECTION 10  —  FIGURES 8–9  (Crime composition)
# =============================================================================
def fig08_crime_composition(crime_cat):
    print("  Fig 8: Crime composition stacked area")
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    yr_starts  = [2010, 2014, 2020, 2022, 2024, 2025]
    yr_labels  = ['Pre-Phase', 'Growth', 'Pand.', 'Post-P.', 'Recent']
    yr_grays   = ['0.97', '0.90', '0.97', '0.90', '0.97']

    for ax, city in zip(axes.flatten(), CITIES):
        sub = crime_cat[crime_cat['city'] == city]
        pivot = (sub.pivot_table(index='year', columns='category',
                                 values='incidents', aggfunc='sum')
                    .reindex(columns=CAT_ORDER, fill_value=0))
        ymax = pivot.sum(axis=1).max()

        for i in range(len(yr_starts) - 1):
            ax.axvspan(yr_starts[i], yr_starts[i + 1],
                       alpha=0.5, color=yr_grays[i], zorder=0)
            mid = (yr_starts[i] + yr_starts[i + 1]) / 2
            ax.text(mid, ymax * 0.96, yr_labels[i],
                    ha='center', va='top', fontsize=6.5,
                    color='#555555', style='italic')

        ax.stackplot(pivot.index,
                     [pivot[c] for c in CAT_ORDER],
                     labels=CAT_ORDER,
                     colors=[CAT_GRAYS[c] for c in CAT_ORDER])
        ax.set_title(city, fontsize=10, fontweight='bold')
        ax.set_xlabel('Year', fontsize=8)
        ax.set_ylabel('Incident Count', fontsize=8)
        ax.set_xlim(2010, 2024)
        for sp in ax.spines.values():
            sp.set_edgecolor('black')

    handles = [mpatches.Patch(facecolor=CAT_GRAYS[c], label=c, edgecolor='black')
               for c in CAT_ORDER]
    fig.legend(handles=handles, loc='lower center', ncol=5,
               fontsize=8, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle('Figure 8. Crime Composition by Category Over Time (Stacked Area)',
                 fontsize=11, fontweight='bold')
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(out('fig08_crime_composition.png'), dpi=150, bbox_inches='tight')
    plt.close()


def fig09_crime_era_composition(crime_cat):
    print("  Fig 9: Crime era composition stacked bar")
    # Era labels as stored in crime_cat (short form with \n)
    era_keys = [
        'Pre-Phase\n2009-2013', 'Growth\n2014-2019',
        'Pandemic\n2020-2021', 'Post-Pandemic\n2022-2023', 'Recent\n2024-2025',
    ]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, city in zip(axes.flatten(), CITIES):
        sub     = crime_cat[crime_cat['city'] == city]
        era_cat = (sub.groupby(['era', 'category'])['incidents']
                      .sum().unstack(fill_value=0)
                      .reindex(columns=CAT_ORDER, fill_value=0))
        available = [e for e in era_keys if e in era_cat.index]
        era_pct  = era_cat.loc[available].div(
            era_cat.loc[available].sum(axis=1), axis=0) * 100

        x = np.arange(len(available))
        bottoms = np.zeros(len(available))
        for cat in CAT_ORDER:
            vals = era_pct[cat].values
            ax.bar(x, vals, bottom=bottoms, label=cat,
                   color=CAT_GRAYS[cat], edgecolor='black', linewidth=0.5, width=0.6)
            for xi, (v, b) in enumerate(zip(vals, bottoms)):
                if v > 5:
                    ax.text(xi, b + v / 2, f'{v:.0f}%',
                            ha='center', va='center', fontsize=6.5,
                            color='white' if float(CAT_GRAYS[cat]) < 0.5 else 'black')
            bottoms += vals

        ax.set_xticks(x)
        ax.set_xticklabels([e.replace('\n', ' ') for e in available],
                           fontsize=6.5, rotation=20, ha='right')
        ax.set_ylim(0, 105)
        ax.set_ylabel('Share (%)', fontsize=8)
        ax.set_title(city, fontsize=10, fontweight='bold')
        for sp in ax.spines.values():
            sp.set_edgecolor('black')

    handles = [mpatches.Patch(facecolor=CAT_GRAYS[c], edgecolor='black', label=c)
               for c in CAT_ORDER]
    fig.legend(handles=handles, loc='lower center', ncol=5,
               fontsize=8, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle('Figure 9. Crime Category Composition (% Share) by Era',
                 fontsize=11, fontweight='bold')
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(out('fig09_crime_era_composition.png'), dpi=150, bbox_inches='tight')
    plt.close()


# =============================================================================
# SECTION 11  —  FIGURES 10–12  (Climate × Violent crime scatters)
# =============================================================================
def _crime_scatter_grid(df, x_var, x_label, title, outname):
    fig, axes = plt.subplots(1, 4, figsize=(14, 4), sharey=False)
    for ax, city in zip(axes, CITIES):
        s   = CITY_STYLES[city]
        sub = df[df['city'] == city].dropna()
        ax.scatter(sub[x_var], sub['violent_incidents'],
                   color=s['color'], marker=s['marker'], s=40, alpha=0.7)
        if len(sub) > 3 and sub[x_var].std() > 0:
            m, b, r, p, _ = stats.linregress(sub[x_var], sub['violent_incidents'])
            xr = np.linspace(sub[x_var].min(), sub[x_var].max(), 50)
            ax.plot(xr, m * xr + b, color='black', lw=1.5)
            star = ('***' if p < 0.001 else '**' if p < 0.01
                    else '*' if p < 0.05 else '')
            ax.set_title(f'{city}\nr={r:.2f}{star}', fontsize=9, fontweight='bold')
        else:
            ax.set_title(city, fontsize=9, fontweight='bold')
        ax.set_xlabel(x_label, fontsize=8)
        ax.set_ylabel('Violent Incidents', fontsize=8)
        for sp in ax.spines.values():
            sp.set_edgecolor('black')
    fig.suptitle(title, fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out(outname), dpi=150, bbox_inches='tight')
    plt.close()


def figs10_12_climate_crime(crime_cat, climate):
    print("  Figs 10–12: Climate vs violent crime")
    climate_cp = climate.copy()
    climate_cp['year'] = climate_cp['year_month'].dt.year
    clim_annual = (climate_cp.groupby(['city', 'year'])
                   .agg(temp_mean=('temp_mean', 'mean'),
                        humidity =('humidity',  'mean'),
                        heat_days=('heat_days', 'sum'))
                   .reset_index())
    violent = (crime_cat[crime_cat['category'] == 'Violent']
               .groupby(['city', 'year'])['incidents'].sum()
               .reset_index()
               .rename(columns={'incidents': 'violent_incidents'}))
    df = violent.merge(clim_annual, on=['city', 'year'])

    _crime_scatter_grid(df, 'temp_mean', 'Annual Mean Temp (°C)',
                        'Figure 10. Annual Mean Temperature vs. Violent Crime by City',
                        'fig10_temp_crime.png')
    _crime_scatter_grid(df, 'heat_days', 'Annual Heat Days (>27°C)',
                        'Figure 11. Annual Heat Days vs. Violent Crime by City',
                        'fig11_heatdays_crime.png')
    _crime_scatter_grid(df, 'humidity', 'Annual Mean Humidity (%)',
                        'Figure 12. Annual Mean Humidity vs. Violent Crime by City',
                        'fig12_humidity_crime.png')


# =============================================================================
# SECTION 12  —  FIGURES 13–14  (Spatial maps)
# =============================================================================
def fig13_spatial_map(merged, crime_cat):
    print("  Fig 13: Spatial crime + sentiment map")
    violent_avg = (crime_cat[crime_cat['category'] == 'Violent']
                   .groupby(['city', 'year'])['incidents'].sum()
                   .reset_index()
                   .groupby('city')['incidents'].mean()
                   .reset_index())
    max_v = violent_avg['incidents'].max()

    era_sent = (merged[merged['era'] == 'Post-Pandemic (2022-2023)']
                .groupby('city')['pct_negative'].mean().reset_index())

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax in axes:
        ax.set_facecolor('0.97')
        add_province_outlines(ax)
        ax.set_xlim(-122, -92)
        ax.set_ylim(47, 62)
        ax.set_xlabel('Longitude', fontsize=8)
        ax.set_ylabel('Latitude', fontsize=8)

    # Panel A: average violent crime volume
    ax = axes[0]
    for _, row in violent_avg.iterrows():
        city = row['city']
        lat, lon = CITY_COORDS[city]
        s = CITY_STYLES[city]
        ax.scatter(lon, lat, s=(row['incidents'] / max_v) * 2000,
                   color=s['color'], alpha=0.6, marker=s['marker'],
                   edgecolors='black', lw=0.8)
        ax.annotate(city, (lon, lat),
                    textcoords='offset points', xytext=(6, 4), fontsize=8)
        ax.annotate(f"{row['incidents']:.0f}", (lon, lat),
                    textcoords='offset points', xytext=(6, -8),
                    fontsize=7, color='#444444')
    ax.set_title('A. Average Annual Violent Crime\nby City (bubble = incident volume)',
                 fontsize=9, fontweight='bold')

    # Panel B: negative sentiment share
    ax = axes[1]
    for _, row in era_sent.iterrows():
        city = row['city']
        lat, lon = CITY_COORDS[city]
        s = CITY_STYLES[city]
        ax.scatter(lon, lat, s=row['pct_negative'] * 25,
                   color=s['color'], alpha=0.6, marker=s['marker'],
                   edgecolors='black', lw=0.8)
        ax.annotate(city, (lon, lat),
                    textcoords='offset points', xytext=(6, 4), fontsize=8)
        ax.annotate(f"{row['pct_negative']:.1f}%\nneg.", (lon, lat),
                    textcoords='offset points', xytext=(6, -10),
                    fontsize=7, color='#444444')
    ax.set_title('B. Mean % Negative Sentiment\nPost-Pandemic Era (2022–2023)',
                 fontsize=9, fontweight='bold')

    fig.suptitle('Figure 13. Spatial Distribution of Crime Volume and Negative Sentiment\n'
                 'Across Prairie Cities',
                 fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out('fig13_spatial_map.png'), dpi=150, bbox_inches='tight')
    plt.close()


def fig14_spatial_overlay(merged, crime_cat, climate):
    print("  Fig 14: Spatial overlay (crime + sentiment)")
    climate_cp = climate.copy()
    climate_cp['year'] = climate_cp['year_month'].dt.year

    clim_era = []
    for city in CITIES:
        for (yr0, yr1), lab in [((2014, 2019), 'Growth Phase (2014-2019)'),
                                 ((2020, 2021), 'Pandemic Phase (2020-2021)')]:
            sub = climate_cp[(climate_cp['city'] == city) &
                              (climate_cp['year'] >= yr0) &
                              (climate_cp['year'] <= yr1)]
            clim_era.append({'city': city, 'era': lab,
                             'heat_days': sub['heat_days'].mean(),
                             'humidity':  sub['humidity'].mean()})
    clim_era_df = pd.DataFrame(clim_era)

    crime_violent = crime_cat[crime_cat['category'] == 'Violent'].copy()
    era_remap = {
        'Pre-Phase\n2009-2013':       'Pre-Phase (2009-2013)',
        'Growth\n2014-2019':          'Growth Phase (2014-2019)',
        'Pandemic\n2020-2021':        'Pandemic Phase (2020-2021)',
        'Post-Pandemic\n2022-2023':   'Post-Pandemic (2022-2023)',
        'Recent\n2024-2025':          'Recent (2024-2025)',
    }
    crime_violent['era_full'] = crime_violent['era'].map(era_remap)
    crime_era_agg = (crime_violent.groupby(['city', 'era_full'])['incidents']
                     .mean().reset_index())
    sent_era = merged.groupby(['city', 'era'])['pct_negative'].mean().reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, era_label in zip(axes, ['Growth Phase (2014-2019)',
                                     'Pandemic Phase (2020-2021)']):
        ax.set_facecolor('0.97')
        add_province_outlines(ax)
        for city in CITIES:
            lat, lon = CITY_COORDS[city]
            s = CITY_STYLES[city]
            c_row  = crime_era_agg[(crime_era_agg['city'] == city) &
                                    (crime_era_agg['era_full'] == era_label)]
            s_row  = sent_era[(sent_era['city'] == city) &
                               (sent_era['era'] == era_label)]
            crime_val = c_row['incidents'].values[0] if len(c_row) > 0 else 0
            sent_val  = s_row['pct_negative'].values[0] if len(s_row) > 0 else 0

            ax.scatter(lon, lat, s=(crime_val / 5000) * 3000,
                       color='0.85', alpha=0.6, edgecolors='black', lw=0.8)
            ax.scatter(lon, lat, s=(sent_val / 100) * 800,
                       color=s['color'], alpha=0.8, marker=s['marker'])
            ax.annotate(f"{city}\nV:{crime_val:.0f}\n%neg:{sent_val:.1f}",
                        (lon, lat), textcoords='offset points',
                        xytext=(5, 5), fontsize=6.5)

        ax.set_xlim(-122, -92)
        ax.set_ylim(47, 62)
        ax.set_xlabel('Longitude', fontsize=8)
        ax.set_ylabel('Latitude', fontsize=8)
        ax.set_title(f'{era_label}\n(outer=crime, inner=neg. sentiment)',
                     fontsize=8, fontweight='bold')
        for sp in ax.spines.values():
            sp.set_edgecolor('black')

    fig.suptitle('Figure 14. Spatial Overlay: Violent Crime Volume and Negative Sentiment\n'
                 'by City and Era',
                 fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out('fig14_spatial_overlay.png'), dpi=150, bbox_inches='tight')
    plt.close()


# =============================================================================
# SECTION 13  —  FIGURE 15  (Seasonal sentiment)
# =============================================================================
def fig15_seasonal_sentiment(merged):
    print("  Fig 15: Seasonal sentiment box plots")
    merged = merged.copy()
    merged['season'] = merged['year_month'].dt.month.map({
        12: 'Winter', 1: 'Winter', 2: 'Winter',
        3:  'Spring',  4: 'Spring',  5: 'Spring',
        6:  'Summer',  7: 'Summer',  8: 'Summer',
        9:  'Fall',   10: 'Fall',   11: 'Fall',
    })

    seasons = ['Winter', 'Spring', 'Summer', 'Fall']
    grays   = ['0.30', '0.60', '0.85', '0.50']

    season_stats = []
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, city in zip(axes.flatten(), CITIES):
        sub  = merged[merged['city'] == city]
        data = [sub[sub['season'] == s]['mean_sentiment'].dropna().values
                for s in seasons]
        bp = ax.boxplot(data, labels=seasons, patch_artist=True,
                        medianprops={'color': 'black', 'lw': 2})
        for patch, g in zip(bp['boxes'], grays):
            patch.set_facecolor(g)
        ax.axhline(0, color='black', lw=0.7, ls='--', alpha=0.5)
        ax.set_title(city, fontsize=10, fontweight='bold')
        ax.set_ylabel('Mean Sentiment', fontsize=8)
        for sp in ax.spines.values():
            sp.set_edgecolor('black')

        for s in seasons:
            vals = sub[sub['season'] == s]['mean_sentiment'].dropna()
            season_stats.append({
                'City': city, 'Season': s, 'N': len(vals),
                'Mean': round(vals.mean(), 4) if len(vals) > 0 else np.nan,
                'Std':  round(vals.std(),  4) if len(vals) > 0 else np.nan,
                'Min':  round(vals.min(),  4) if len(vals) > 0 else np.nan,
                'Max':  round(vals.max(),  4) if len(vals) > 0 else np.nan,
            })

    fig.suptitle('Figure 15. Seasonal Sentiment Distribution by City (Box Plots)',
                 fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out('fig15_seasonal_sentiment.png'), dpi=150, bbox_inches='tight')
    plt.close()

    pd.DataFrame(season_stats).to_csv(out('seasonal_sentiment_stats.csv'), index=False)


# =============================================================================
# SECTION 14  —  FIGURE 16  (Correlation heatmaps)
# =============================================================================
def fig16_corr_heatmaps(corr_sent_df, corr_crime_df):
    print("  Fig 16: Correlation heatmaps")
    var_labels = {
        'temp_mean': 'Mean Temp.',    'temp_anomaly': 'Temp. Anomaly',
        'humidity':  'Humidity',      'heat_days':    'Heat Days',
        'cold_days': 'Cold Days',     'snow_ground':  'Snow on Ground',
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, df, col_order, title in [
        (axes[0], corr_sent_df,
         ['temp_mean', 'temp_anomaly', 'humidity', 'snow_ground', 'heat_days', 'cold_days'],
         'A. Climate Variables vs. Sentiment\n(Pearson r)'),
        (axes[1], corr_crime_df,
         ['temp_mean', 'temp_anomaly', 'humidity', 'heat_days', 'cold_days'],
         'B. Climate Variables vs. Violent Crime\n(Pearson r, Annual)'),
    ]:
        pivot  = df.pivot(index='City', columns='Variable', values='Pearson_r')
        cols   = [c for c in col_order if c in pivot.columns]
        pivot  = pivot[cols]
        vmax   = 0.6 if 'Sentiment' in title else 0.9

        im = ax.imshow(pivot.values, cmap='Greys', aspect='auto',
                       vmin=-vmax, vmax=vmax)
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels([var_labels.get(c, c) for c in cols],
                           fontsize=8, rotation=30, ha='right')
        ax.set_yticks(range(len(CITIES)))
        ax.set_yticklabels(CITIES, fontsize=9)

        for i, city in enumerate(CITIES):
            for j, col in enumerate(cols):
                v   = pivot.values[i, j]
                sig = df[(df['City'] == city) & (df['Variable'] == col)]['Sig'].values
                sig_str = sig[0] if len(sig) > 0 else ''
                color   = 'white' if abs(v) > vmax * 0.6 else 'black'
                ax.text(j, i, f'{v:.2f}{sig_str}',
                        ha='center', va='center', fontsize=7.5, color=color)

        plt.colorbar(im, ax=ax, label='Pearson r', shrink=0.8)
        ax.set_title(title, fontsize=9, fontweight='bold')

    fig.suptitle('Figure 16. Climate–Sentiment and Climate–Crime Correlation Heatmaps',
                 fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out('fig16_corr_heatmaps.png'), dpi=150, bbox_inches='tight')
    plt.close()


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    print("=" * 70)
    print("Prairie Climate–Crime–Sentiment Analysis Pipeline")
    print("=" * 70)

    # 1. Load data
    reddit  = load_reddit()
    climate = load_climate()
    crime_cat, crime_total = load_crime()

    # 2. Merge and correlations
    merged, corr_sent = build_merged_and_correlations(reddit, climate)
    crime_clim_df, corr_crime = compute_crime_climate_correlations(crime_cat, climate)

    # 3. Volatility
    vol_df = compute_volatility(reddit)

    # 4. Figures
    print("\nGenerating figures...")
    fig01_sentiment_trajectory(reddit)
    fig02_volatility_bars(vol_df)
    fig03_rolling_volatility(reddit)
    fig04_volatility_heatmap(vol_df)
    fig05_temp_anomaly_sentiment(merged)
    fig06_heat_sentiment(merged)
    fig07_humidity_sentiment(merged)
    fig08_crime_composition(crime_cat)
    fig09_crime_era_composition(crime_cat)
    figs10_12_climate_crime(crime_cat, climate)
    fig13_spatial_map(merged, crime_cat)
    fig14_spatial_overlay(merged, crime_cat, climate)
    fig15_seasonal_sentiment(merged)
    fig16_corr_heatmaps(corr_sent, corr_crime)

    figs = sorted(f for f in os.listdir(OUTPUT_DIR) if f.endswith('.png'))
    print(f"\nDone. {len(figs)} figures written to '{OUTPUT_DIR}/'")
    for f in figs:
        print(f"  {f}")