import streamlit as st
import pandas as pd
import time
import math
from datetime import datetime
from fpdf import FPDF
import plotly.graph_objects as go

st.set_page_config(page_title="Diver Decompression Planner", layout="wide")

st.markdown("""
<style>
div.scrolling-wrapper {
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    gap: 15px;
    padding: 10px 5px;
    margin-bottom: 10px;
    min-height: 120px; 
    align-items: center;
}
div.card {
    flex: 0 0 auto;
    background-color: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 10px;
    width: 170px;
    text-align: center;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    justify-content: center;
    transition: all 0.3s ease;
    position: relative;
}

/* ACTIVE STATE (Current Stop) */
div.card.active {
    border-left: 6px solid #00CC66 !important;
    background-color: #f0fff4 !important;
    transform: scale(1.05);
    box-shadow: 4px 4px 12px rgba(0, 204, 102, 0.25);
    z-index: 10;
}

/* PAUSED STATE (During Air Break) */
div.card.paused {
    border-left: 6px solid #FFA500 !important;
    background-color: #fff3e0 !important;
}

/* DONE STATE (Completed Stop) */
div.card.done {
    background-color: #e0e0e0 !important;
    border-color: #cccccc !important;
    opacity: 0.5;
}
div.card.done .card-time, div.card.done .card-depth {
    color: #888888 !important;
}

/* TYPOGRAPHY */
div.card-time {
    font-size: 1.1rem;
    font-weight: bold;
    color: #333;
    margin-bottom: 2px;
}
div.card-depth {
    font-size: 0.85rem;
    color: #666;
    font-weight: 500;
    margin-bottom: 5px;
}
div.card-countdown {
    font-size: 1.0rem;
    font-weight: bold;
    color: #00CC66;
    border-top: 1px solid #e0e0e0;
    padding-top: 4px;
    margin-top: 2px;
}
div.card-paused-text {
    font-size: 0.9rem;
    font-weight: bold;
    color: #FFA500;
    border-top: 1px solid #e0e0e0;
    padding-top: 4px;
    margin-top: 2px;
    text-transform: uppercase;
}

/* SCROLLBAR */
div.scrolling-wrapper::-webkit-scrollbar {
    height: 8px;
}
div.scrolling-wrapper::-webkit-scrollbar-thumb {
    background-color: #cccccc;
    border-radius: 4px;
}

/* UI TWEAKS */
div[data-testid="stRadio"] > label {
    display: none;
}
div[role="radiogroup"] {
    gap: 10px;
}
.status-box-green {
    background-color: #e8f5e9;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid #c8e6c9;
    color: #2e7d32;
    font-weight: bold;
    text-align: center;
}
.status-box-red {
    background-color: #ffebee;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid #ffcdd2;
    color: #c62828;
    text-align: center;
    font-weight: bold;
}
.chamber-status-box {
    background-color: #e8f5e9;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid #c8e6c9;
    color: #2e7d32;
    font-weight: bold;
    text-align: center;
}
.chamber-unavailable-box {
    background-color: #ffebee;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid #ffcdd2;
    color: #c62828;
    text-align: center;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

def parse_time_str(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip()
    if ':' in val_str:
        parts = val_str.split(':')
        return float(parts[0]) + float(parts[1])/60.0
    return float(val_str)

@st.cache_data
def load_data():
    try:
        profiles = pd.read_csv('dive_profiles.csv')
        stops = pd.read_csv('deco_stops.csv')
    except FileNotFoundError:
        st.error("CSV files not found. Please ensure 'dive_profiles.csv' and 'deco_stops.csv' are in the app folder.")
        profiles, stops = pd.DataFrame(), pd.DataFrame()
        
    try:
        p_us = pd.read_csv('dive_profiles_us.csv')
        s_us = pd.read_csv('deco_stops_us.csv')
        
        if 'dive_depth_fsw' in p_us.columns:
            p_us['dive_depth_m'] = p_us['dive_depth_fsw'].astype(float) * 0.3048
        if 'stop_depth_fsw' in s_us.columns:
            s_us['stop_depth_m'] = s_us['stop_depth_fsw'].astype(float) * 0.3048
            
        for col in ['bottom_time_min', 'ascent_to_1st_stop_min']:
            if col in p_us.columns:
                p_us[col] = p_us[col].apply(parse_time_str)
        if 'duration_air_min' in s_us.columns:
            s_us['duration_air_min'] = s_us['duration_air_min'].apply(parse_time_str)
            
    except FileNotFoundError:
        p_us, s_us = pd.DataFrame(), pd.DataFrame()

    try:
        p_swe = pd.read_csv('dive_profiles_swem.csv')
        s_swe = pd.read_csv('deco_stops_swem.csv')
        
        for col in ['bottom_time_min', 'ascent_to_1st_stop_min']:
            if col in p_swe.columns:
                p_swe[col] = p_swe[col].apply(parse_time_str)
        if 'duration_air_min' in s_swe.columns:
            s_swe['duration_air_min'] = s_swe['duration_air_min'].apply(parse_time_str)
            
    except FileNotFoundError:
        p_swe, s_swe = pd.DataFrame(), pd.DataFrame()

    return profiles, stops, p_us, s_us, p_swe, s_swe

def get_safe_table_depth(input_depth, profiles_df):
    if profiles_df.empty: return input_depth
    unique_depths = sorted(profiles_df['dive_depth_m'].unique())
    for d in unique_depths:
        if d >= input_depth: return d
    return unique_depths[-1]

def get_next_depth(current_table_depth, profiles_df):
    unique_depths = sorted(profiles_df['dive_depth_m'].unique())
    try:
        curr_idx = unique_depths.index(current_table_depth)
        if curr_idx + 1 < len(unique_depths):
            return unique_depths[curr_idx + 1]
    except ValueError:
        pass
    return current_table_depth

def calculate_o2_time(air_time, depth):
    if depth < 18: return math.ceil(air_time / 2)
    return None

def calculate_profile_index(subset, elapsed_min, risk_active, is_longer):
    if subset.empty: return -1
    valid_times = subset[subset['bottom_time_min'] > elapsed_min]
    if not valid_times.empty:
        base_idx = subset.index.get_loc(valid_times.index[0])
    else:
        base_idx = len(subset) - 1
    
    safety_adder = 1 if risk_active else 0
    longer_adder = 1 if is_longer else 0
    
    final_idx = base_idx + safety_adder + longer_adder
    if final_idx >= len(subset):
        final_idx = len(subset) - 1
        
    return final_idx

def sanitize_pl(text):
    if text is None: return ""
    text = str(text)
    repls = {
        'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z',
        'Ą':'A', 'Ć':'C', 'Ę':'E', 'Ł':'L', 'Ń':'N', 'Ó':'O', 'Ś':'S', 'Ź':'Z', 'Ż':'Z'
    }
    for k, v in repls.items(): text = text.replace(k, v)
    return text

def generate_dive_profile_chart(actual_time, used_o2, logbook_data, profiles_df, stops_df, p_us_df, s_us_df, p_swe_df, s_swe_df):
    profile_id = logbook_data.get('final_profile_id')
    break_events = logbook_data.get('break_events', []) 
    pre_deco_break = logbook_data.get('pre_deco_break', False)
    planned_depth = logbook_data.get('depth', 0)
    
    if profile_id is None:
        return None

    fig = go.Figure()
    legends_shown = set()

    def plot_segment(x0, x1, y0, y1, color, width, dash='solid', legend_key=None, legend_label=None):
        show_leg = False
        if legend_key and legend_key not in legends_shown:
            show_leg = True
            legends_shown.add(legend_key)
            
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode='lines',
            line=dict(color=color, width=width, dash=dash),
            name=legend_label if legend_label else (legend_key if legend_key else ""),
            showlegend=show_leg,
            legendgroup=legend_key if legend_key else "unnamed",
            hovertemplate="Czas: %{x:.1f} min<br>Głębokość: %{y:.1f} m<extra></extra>"
        ))

    row = profiles_df[profiles_df['profile_id'] == profile_id].iloc[0]
    plot_depth = row['dive_depth_m']
    my_stops = stops_df[stops_df['profile_id'] == profile_id].sort_values('stop_depth_m', ascending=False)
    ascent_to_1st = row['ascent_to_1st_stop_min']
    
    curr_x, curr_y = 0, 0
    next_x, next_y = curr_x + 2, plot_depth
    plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'solid', 'PL_Air', 'PL Profil (Główny)')
    curr_x, curr_y = next_x, next_y
    
    bt_end = max(actual_time, 2 + 1)
    plot_segment(curr_x, bt_end, curr_y, curr_y, 'black', 2, 'solid', 'PL_Air')
    curr_x = bt_end
    
    if pre_deco_break:
        next_x, next_y = curr_x + 1, 0
        plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'dot', 'PL_Air')
        curr_x, curr_y = next_x, next_y
        
        next_x = curr_x + 5
        plot_segment(curr_x, next_x, curr_y, curr_y, 'black', 2, 'solid', 'PL_Air')
        curr_x = next_x
        
        next_x, next_y = curr_x + 1, plot_depth
        plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'dot', 'PL_Air')
        curr_x, curr_y = next_x, next_y
        
        d_o2_check = calculate_o2_time(10, plot_depth)
        is_o2_flush = (used_o2 and d_o2_check is not None)
        c_flush, w_flush, l_key, l_lbl = ('#00BFFF', 3, 'PL_O2', 'PL Tlen (O2)') if is_o2_flush else ('black', 2, 'PL_Air', None)
        next_x = curr_x + 10
        plot_segment(curr_x, next_x, curr_y, curr_y, c_flush, w_flush, 'solid', l_key, l_lbl)
        curr_x = next_x

    target_depth = my_stops.iloc[0]['stop_depth_m'] if not my_stops.empty else 0
    next_x, next_y = curr_x + ascent_to_1st, target_depth
    plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'solid', 'PL_Air')
    curr_x, curr_y = next_x, next_y
    
    if not my_stops.empty:
        for i, (_, stop) in enumerate(my_stops.iterrows()):
            depth = stop['stop_depth_m']
            if curr_y > depth:
                next_x, next_y = curr_x + 1, depth
                plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'solid', 'PL_Air')
                curr_x, curr_y = next_x, next_y
            
            if (i + 1) in break_events:
                next_x, next_y = curr_x + 1, 0
                plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'dot', 'PL_Air')
                curr_x, curr_y = next_x, next_y
                next_x = curr_x + 5
                plot_segment(curr_x, next_x, curr_y, curr_y, 'black', 2, 'solid', 'PL_Air')
                curr_x = next_x
                next_x, next_y = curr_x + 1, depth
                plot_segment(curr_x, next_x, curr_y, next_y, 'black', 2, 'dot', 'PL_Air')
                curr_x, curr_y = next_x, next_y
                d_o2_check = calculate_o2_time(10, depth)
                is_o2_flush = (used_o2 and d_o2_check is not None)
                c_flush, w_flush, l_key, l_lbl = ('#00BFFF', 3, 'PL_O2', 'PL Tlen (O2)') if is_o2_flush else ('black', 2, 'PL_Air', None)
                next_x = curr_x + 10
                plot_segment(curr_x, next_x, curr_y, curr_y, c_flush, w_flush, 'solid', l_key, l_lbl)
                curr_x = next_x
            
            d_air = stop['duration_air_min']
            d_o2 = calculate_o2_time(d_air, depth)
            is_o2_segment = (used_o2 and d_o2 is not None)
            dur = d_o2 if is_o2_segment else d_air
            c_seg, w_seg, l_key, l_lbl = ('#00BFFF', 3, 'PL_O2', 'PL Tlen (O2)') if is_o2_segment else ('black', 2, 'PL_Air', None)
            
            next_x = curr_x + dur
            plot_segment(curr_x, next_x, curr_y, curr_y, c_seg, w_seg, 'solid', l_key, l_lbl)
            curr_x = next_x
            
    if curr_y > 0:
        next_x = curr_x + 1
        plot_segment(curr_x, next_x, curr_y, 0, 'black', 2, 'solid', 'PL_Air')

    us_title_ext = ""
    if not p_us_df.empty and not s_us_df.empty:
        us_depth = get_safe_table_depth(planned_depth, p_us_df)
        us_subset = p_us_df[p_us_df['dive_depth_m'] == us_depth].sort_values('bottom_time_min')
        us_idx = calculate_profile_index(us_subset, actual_time, risk_active=False, is_longer=False)
        
        if us_idx != -1:
            us_profile_id = us_subset.iloc[us_idx]['profile_id']
            us_row = p_us_df[p_us_df['profile_id'] == us_profile_id].iloc[0]
            us_plot_depth = us_row['dive_depth_m']
            us_stops = s_us_df[s_us_df['profile_id'] == us_profile_id].sort_values('stop_depth_m', ascending=False)
            us_ascent = us_row['ascent_to_1st_stop_min']
            
            us_title_ext = f" | US: {us_plot_depth:.1f}m"
            curr_x, curr_y = 0, 0
            
            next_x, next_y = curr_x + 2, us_plot_depth
            plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dash', 'US_Air', 'US Navy (Porównanie)')
            curr_x, curr_y = next_x, next_y
            
            plot_segment(curr_x, bt_end, curr_y, curr_y, 'red', 2, 'dash', 'US_Air')
            curr_x = bt_end
            
            if pre_deco_break:
                next_x, next_y = curr_x + 1, 0
                plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dot', 'US_Air')
                curr_x, curr_y = next_x, next_y
                next_x = curr_x + 5
                plot_segment(curr_x, next_x, curr_y, curr_y, 'red', 2, 'dash', 'US_Air')
                curr_x = next_x
                next_x, next_y = curr_x + 1, us_plot_depth
                plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dot', 'US_Air')
                curr_x, curr_y = next_x, next_y
                
                is_us_o2_flush = (used_o2 and calculate_o2_time(10, us_plot_depth) is not None)
                c_flush, w_flush, l_key, l_lbl = ('#FF6347', 3, 'US_O2', 'US Navy Tlen') if is_us_o2_flush else ('red', 2, 'US_Air', None)
                next_x = curr_x + 10
                plot_segment(curr_x, next_x, curr_y, curr_y, c_flush, w_flush, 'dash', l_key, l_lbl)
                curr_x = next_x
                
            target_depth = us_stops.iloc[0]['stop_depth_m'] if not us_stops.empty else 0
            next_x, next_y = curr_x + us_ascent, target_depth
            plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dash', 'US_Air')
            curr_x, curr_y = next_x, next_y
            
            if not us_stops.empty:
                for i, (_, stop) in enumerate(us_stops.iterrows()):
                    depth = stop['stop_depth_m']
                    if curr_y > depth:
                        next_x, next_y = curr_x + 1, depth
                        plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dash', 'US_Air')
                        curr_x, curr_y = next_x, next_y
                    
                    if (i+1) in break_events:
                        next_x, next_y = curr_x + 1, 0
                        plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dot', 'US_Air')
                        curr_x, curr_y = next_x, next_y
                        next_x = curr_x + 5
                        plot_segment(curr_x, next_x, curr_y, curr_y, 'red', 2, 'dash', 'US_Air')
                        curr_x = next_x
                        next_x, next_y = curr_x + 1, depth
                        plot_segment(curr_x, next_x, curr_y, next_y, 'red', 2, 'dot', 'US_Air')
                        curr_x, curr_y = next_x, next_y
                        
                        is_us_o2_flush = (used_o2 and calculate_o2_time(10, depth) is not None)
                        c_flush, w_flush, l_key, l_lbl = ('#FF6347', 3, 'US_O2', 'US Navy Tlen') if is_us_o2_flush else ('red', 2, 'US_Air', None)
                        next_x = curr_x + 10
                        plot_segment(curr_x, next_x, curr_y, curr_y, c_flush, w_flush, 'dash', l_key, l_lbl)
                        curr_x = next_x

                    d_air = stop['duration_air_min']
                    d_o2 = calculate_o2_time(d_air, depth)
                    is_us_o2 = (used_o2 and d_o2 is not None)
                    dur = d_o2 if is_us_o2 else d_air
                    c_seg, w_seg, l_key, l_lbl = ('#FF6347', 3, 'US_O2', 'US Navy Tlen') if is_us_o2 else ('red', 2, 'US_Air', None)
                    
                    next_x = curr_x + dur
                    plot_segment(curr_x, next_x, curr_y, curr_y, c_seg, w_seg, 'dash', l_key, l_lbl)
                    curr_x = next_x
            
            if curr_y > 0:
                next_x = curr_x + 1
                plot_segment(curr_x, next_x, curr_y, 0, 'red', 2, 'dash', 'US_Air')


    swe_title_ext = ""
    if not p_swe_df.empty and not s_swe_df.empty:
        swe_depth = get_safe_table_depth(planned_depth, p_swe_df)
        swe_subset = p_swe_df[p_swe_df['dive_depth_m'] == swe_depth].sort_values('bottom_time_min')
        swe_idx = calculate_profile_index(swe_subset, actual_time, risk_active=False, is_longer=False)
        
        if swe_idx != -1:
            swe_profile_id = swe_subset.iloc[swe_idx]['profile_id']
            swe_row = p_swe_df[p_swe_df['profile_id'] == swe_profile_id].iloc[0]
            swe_plot_depth = swe_row['dive_depth_m']
            swe_stops = s_swe_df[s_swe_df['profile_id'] == swe_profile_id].sort_values('stop_depth_m', ascending=False)
            swe_ascent = swe_row['ascent_to_1st_stop_min']
            
            swe_title_ext = f" | SWE: {swe_plot_depth:.1f}m"
            curr_x, curr_y = 0, 0
            
            next_x, next_y = curr_x + 2, swe_plot_depth
            plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dash', 'SWE_Air', 'Szwecja (Porównanie)')
            curr_x, curr_y = next_x, next_y
            
            plot_segment(curr_x, bt_end, curr_y, curr_y, 'green', 2, 'dash', 'SWE_Air')
            curr_x = bt_end
            
            if pre_deco_break:
                next_x, next_y = curr_x + 1, 0
                plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dot', 'SWE_Air')
                curr_x, curr_y = next_x, next_y
                next_x = curr_x + 5
                plot_segment(curr_x, next_x, curr_y, curr_y, 'green', 2, 'dash', 'SWE_Air')
                curr_x = next_x
                next_x, next_y = curr_x + 1, swe_plot_depth
                plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dot', 'SWE_Air')
                curr_x, curr_y = next_x, next_y
                
                is_swe_o2_flush = (used_o2 and calculate_o2_time(10, swe_plot_depth) is not None)
                c_flush, w_flush, l_key, l_lbl = ('#32CD32', 3, 'SWE_O2', 'Szwecja Tlen') if is_swe_o2_flush else ('green', 2, 'SWE_Air', None)
                next_x = curr_x + 10
                plot_segment(curr_x, next_x, curr_y, curr_y, c_flush, w_flush, 'dash', l_key, l_lbl)
                curr_x = next_x
                
            target_depth = swe_stops.iloc[0]['stop_depth_m'] if not swe_stops.empty else 0
            next_x, next_y = curr_x + swe_ascent, target_depth
            plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dash', 'SWE_Air')
            curr_x, curr_y = next_x, next_y
            
            if not swe_stops.empty:
                for i, (_, stop) in enumerate(swe_stops.iterrows()):
                    depth = stop['stop_depth_m']
                    if curr_y > depth:
                        next_x, next_y = curr_x + 1, depth
                        plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dash', 'SWE_Air')
                        curr_x, curr_y = next_x, next_y
                    
                    if (i+1) in break_events:
                        next_x, next_y = curr_x + 1, 0
                        plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dot', 'SWE_Air')
                        curr_x, curr_y = next_x, next_y
                        next_x = curr_x + 5
                        plot_segment(curr_x, next_x, curr_y, curr_y, 'green', 2, 'dash', 'SWE_Air')
                        curr_x = next_x
                        next_x, next_y = curr_x + 1, depth
                        plot_segment(curr_x, next_x, curr_y, next_y, 'green', 2, 'dot', 'SWE_Air')
                        curr_x, curr_y = next_x, next_y
                        
                        is_swe_o2_flush = (used_o2 and calculate_o2_time(10, depth) is not None)
                        c_flush, w_flush, l_key, l_lbl = ('#32CD32', 3, 'SWE_O2', 'Szwecja Tlen') if is_swe_o2_flush else ('green', 2, 'SWE_Air', None)
                        next_x = curr_x + 10
                        plot_segment(curr_x, next_x, curr_y, curr_y, c_flush, w_flush, 'dash', l_key, l_lbl)
                        curr_x = next_x

                    d_air = stop['duration_air_min']
                    d_o2 = calculate_o2_time(d_air, depth)
                    is_swe_o2 = (used_o2 and d_o2 is not None)
                    dur = d_o2 if is_swe_o2 else d_air
                    c_seg, w_seg, l_key, l_lbl = ('#32CD32', 3, 'SWE_O2', 'Szwecja Tlen') if is_swe_o2 else ('green', 2, 'SWE_Air', None)
                    
                    next_x = curr_x + dur
                    plot_segment(curr_x, next_x, curr_y, curr_y, c_seg, w_seg, 'dash', l_key, l_lbl)
                    curr_x = next_x
            
            if curr_y > 0:
                next_x = curr_x + 1
                plot_segment(curr_x, next_x, curr_y, 0, 'green', 2, 'dash', 'SWE_Air')

    fig.update_layout(
        title=f"Profil Nurkowania [Głębokość Tabeli: {plot_depth}m{us_title_ext}{swe_title_ext} | Czas Dna: {bt_end:.1f} min]",
        xaxis_title="Czas (min)",
        yaxis_title="Głębokość (m)",
        yaxis=dict(
            autorange="reversed",
            showspikes=True, spikemode="toaxis+across", spikesnap="cursor",
            showline=True, showgrid=True, gridcolor='rgba(200,200,200,0.4)',
            zeroline=True, zerolinecolor='black'
        ),
        xaxis=dict(
            showspikes=True, spikemode="toaxis+across", spikesnap="cursor",
            showline=True, showgrid=True, gridcolor='rgba(200,200,200,0.4)',
            zeroline=True, zerolinecolor='black'
        ),
        hovermode="closest",
        plot_bgcolor="white",
        legend=dict(x=0.75, y=0.05, bgcolor='rgba(255,255,255,0.8)', bordercolor='lightgray', borderwidth=1),
        margin=dict(l=40, r=40, t=60, b=40)
    )

    return fig

def create_pdf(entries):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "RAPORT Z NURKOWANIA", 0, 1, 'C')
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 5)
    line_height = 8
    headers = [("Lp.", 6), ("Data", 14), ("Nazwisko", 20), ("Rejon/Gl.", 15),("Start", 8), ("Gleb.", 8), ("St.Deco", 9), ("Dzwon", 9),("Koniec", 8), ("T.Woda", 9), ("T.Komora", 10), ("T.Ogol", 9),("T.Pobyt", 10), ("Czynnik", 9), ("Sprzet", 12),("Sprawdz.", 12), ("Prace / Dezynfekcja", 35), ("Stan M.", 8),("T.Wody", 8), ("T.Pow.", 8), ("Prad", 8), ("Podpis", 25)]
    for header, width in headers: pdf.cell(width, line_height, header, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", '', 5)
    
    keys_in_order = [
        "lp", "data", "nazwisko", "rejon", "start_zanurzania", "glebokosc", 
        "start_wynurzania", "zamkniecie_dzwonu", "koniec_wynurzania", "czas_deco_woda", 
        "czas_deco_komora", "czas_ogolny", "czas_komora_pobyt", "czynnik", "sprzet", 
        "sprawdzenie", "uwagi", "stan_morza", "temp_wody", "temp_pow", "prad", "podpis"
    ]
    
    for row in entries:
        data_values = [sanitize_pl(row.get(key, "")) for key in keys_in_order]
        for i, value in enumerate(data_values):
            width = headers[i][1]
            max_len = int(width * 2.5) 
            display_text = (value[:max_len] + '..') if len(value) > max_len else value
            pdf.cell(width, line_height, display_text, 1, 0, 'C')
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1', 'replace')

if 'page' not in st.session_state: st.session_state.page = 'input'
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'planned_depth' not in st.session_state: st.session_state.planned_depth = 0
if 'safety_buffer_active' not in st.session_state: st.session_state.safety_buffer_active = False
if 'deco_phase_active' not in st.session_state: st.session_state.deco_phase_active = False
if 'deco_start_time' not in st.session_state: st.session_state.deco_start_time = None
if 'locked_bottom_time_min' not in st.session_state: st.session_state.locked_bottom_time_min = 0
if 'locked_bottom_time_sec' not in st.session_state: st.session_state.locked_bottom_time_sec = 0

if 'locked_plan_name' not in st.session_state: st.session_state.locked_plan_name = None
if 'locked_profile_id' not in st.session_state: st.session_state.locked_profile_id = None
if 'current_selection_name' not in st.session_state: st.session_state.current_selection_name = "Current Plan"

if 'deco_step_index' not in st.session_state: st.session_state.deco_step_index = 0
if 'deco_step_progress_air_sec' not in st.session_state: st.session_state.deco_step_progress_air_sec = 0.0
if 'deco_last_tick' not in st.session_state: st.session_state.deco_last_tick = None
if 'deco_o2_enabled' not in st.session_state: st.session_state.deco_o2_enabled = False
if 'break_phase' not in st.session_state: st.session_state.break_phase = None 
if 'break_start_time' not in st.session_state: st.session_state.break_start_time = None
if 'break_duration' not in st.session_state: st.session_state.break_duration = 0
if 'break_events' not in st.session_state: st.session_state.break_events = []
if 'pre_deco_break_occurred' not in st.session_state: st.session_state.pre_deco_break_occurred = False
if 'break_used_in_this_dive' not in st.session_state: st.session_state.break_used_in_this_dive = False

if 'logbook_context' not in st.session_state: st.session_state.logbook_context = {}
if 'logbook_entries' not in st.session_state: st.session_state.logbook_entries = []
if 'form_lp' not in st.session_state: st.session_state.form_lp = 1
if 'active_profile_id_tracker' not in st.session_state: st.session_state.active_profile_id_tracker = None

def render_input_view(placeholder):
    with placeholder.container():
        st.title("🤿 Start New Dive")
        depth_input = st.number_input("Planned Depth (m):", min_value=0, value=12, step=1, key="input_depth")
        st.markdown("### Safety Risk Factors")
        c1, c2 = st.columns(2)
        with c1: f1 = st.checkbox("Not trained diver", key="chk_1"); f2 = st.checkbox("DCS likelihood", key="chk_2"); f3 = st.checkbox("Doing very hard work", key="chk_3")
        with c2: f4 = st.checkbox("Water temperature below 10°C", key="chk_4"); f5 = st.checkbox("Other non-ideal scenario", key="chk_5")
        is_depth_valid = depth_input > 0
        if not is_depth_valid: st.warning("⚠️ Please provide a depth value to enable the Start button.")
        if st.button("Start Dive", type="primary", disabled=not is_depth_valid):
            st.session_state.safety_buffer_active = any([f1, f2, f3, f4, f5])
            st.session_state.planned_depth = depth_input
            st.session_state.start_time = time.time()
            st.session_state.page = 'results'
            st.session_state.debug_manual_mode = False; st.session_state.debug_manual_time = 0
            st.session_state.deco_phase_active = False; st.session_state.deco_start_time = None
            st.session_state.locked_bottom_time_min = 0; st.session_state.locked_bottom_time_sec = 0
            
            st.session_state.locked_plan_name = None
            st.session_state.locked_profile_id = None
            st.session_state.current_selection_name = "Current Plan"
            
            st.session_state.deco_step_index = 0; st.session_state.deco_step_progress_air_sec = 0.0
            st.session_state.deco_last_tick = None; st.session_state.deco_o2_enabled = False
            st.session_state.break_phase = None; st.session_state.break_start_time = None; st.session_state.break_duration = 0
            st.session_state.break_events = []; st.session_state.pre_deco_break_occurred = False
            st.session_state.break_used_in_this_dive = False
            st.session_state.logbook_context = {}; st.session_state.logbook_entries = []; st.session_state.form_lp = 1
            st.session_state.active_profile_id_tracker = None
            placeholder.empty(); st.rerun()


def render_results_view(placeholder):
    profiles_df, stops_df, p_us, s_us, p_swe, s_swe = load_data()
    with placeholder.container():
        @st.fragment(run_every=1)
        def live_timer_header():
            current_timestamp = time.time()
            if st.session_state.get('debug_manual_mode', False): raw_elapsed_min = st.session_state.get('debug_manual_time', 0); raw_elapsed_sec = 0; is_debug = True
            else: elapsed_seconds = int(current_timestamp - st.session_state.start_time); raw_elapsed_min = elapsed_seconds // 60; raw_elapsed_sec = elapsed_seconds % 60; is_debug = False
            
            if st.session_state.deco_phase_active:
                calculation_time_min = st.session_state.locked_bottom_time_min; display_min = st.session_state.locked_bottom_time_min; display_sec = st.session_state.locked_bottom_time_sec 
                deco_seconds_total = int(current_timestamp - st.session_state.deco_start_time); deco_min = deco_seconds_total // 60; deco_sec = deco_seconds_total % 60
                status_text = "BOTTOM TIME (ENDED)"; timer_color = "#888888" 
            else:
                calculation_time_min = raw_elapsed_min; display_min = raw_elapsed_min; display_sec = raw_elapsed_sec; deco_min = 0; deco_sec = 0
                if is_debug: timer_color = "#3399FF"; status_text = "MANUAL DEBUG TIME"
                elif st.session_state.safety_buffer_active: timer_color = "#FFA500"; status_text = "BOTTOM TIME"
                else: timer_color = "#00CC66"; status_text = "BOTTOM TIME"

            user_depth = st.session_state.planned_depth; risk_active = st.session_state.safety_buffer_active
            current_table_depth = get_safe_table_depth(user_depth, profiles_df)
            current_subset = profiles_df[profiles_df['dive_depth_m'] == current_table_depth].sort_values('bottom_time_min')
            idx_current = calculate_profile_index(current_subset, calculation_time_min, risk_active, is_longer=False)
            if idx_current != -1: row = current_subset.iloc[idx_current]; current_profile_str = f"{current_table_depth} / {row['bottom_time_min']}"; idx_raw = calculate_profile_index(current_subset, calculation_time_min, risk_active=False, is_longer=False); safety_visual = (idx_current > idx_raw)
            else: current_profile_str = "No Data"; safety_visual = False

            c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
            with c1: st.metric("PLANNED DEPTH", f"{user_depth}m", delta=f"Using Table: {current_table_depth}m" if current_table_depth != user_depth else None, delta_color="off")
            with c2: st.markdown(f"<h1 style='text-align: center; color: {timer_color}; margin: 0; padding: 0;'>{display_min:02d}:{display_sec:02d}</h1>", unsafe_allow_html=True); st.caption(f"<p style='text-align: center;'>{status_text}</p>", unsafe_allow_html=True)
            with c3:
                if st.session_state.deco_phase_active: st.markdown(f"<h1 style='text-align: center; color: #3399FF; margin: 0; padding: 0;'>{deco_min:02d}:{deco_sec:02d}</h1>", unsafe_allow_html=True); st.caption(f"<p style='text-align: center;'>DECOMPRESSION TIME</p>", unsafe_allow_html=True)
                else: st.markdown("") 
            with c4: st.metric("PROFILE", current_profile_str, delta="Safety (+1)" if safety_visual else None)
            st.divider()

            is_plan_locked = st.session_state.deco_phase_active or st.session_state.pre_deco_break_occurred

            col_menu, col_o2 = st.columns([3, 1])
            with col_menu: 
                st.markdown("### Next Stops Plan")
                
                if is_plan_locked:
                    st.markdown(f"<div style='padding: 5px 10px; margin-bottom: 10px; border-radius: 5px; background-color: #e8f5e9; border: 1px solid #00CC66; color: #00CC66; font-size: 0.9rem;'><strong>Aktywny plan w tle:</strong> {st.session_state.locked_plan_name}</div>", unsafe_allow_html=True)
                
                scenario_options = ["Current Plan", "Deeper", "Longer", "Deeper & Longer"]
                selection = st.radio("Select Scenario:", scenario_options, horizontal=True, label_visibility="collapsed", key="scenario_radio")
            
            with col_o2: 
                st.markdown("### ") 
                st.session_state.deco_o2_enabled = st.checkbox("Using Oxygen", value=st.session_state.deco_o2_enabled)

            target_profile_id = None
            if selection == "Current Plan": target_idx = calculate_profile_index(current_subset, calculation_time_min, risk_active, is_longer=False); target_profile_id = current_subset.iloc[target_idx]['profile_id'] if target_idx != -1 else None
            elif selection == "Longer": target_idx = calculate_profile_index(current_subset, calculation_time_min, risk_active, is_longer=True); target_profile_id = current_subset.iloc[target_idx]['profile_id'] if target_idx != -1 else None
            elif selection == "Deeper": next_depth = get_next_depth(current_table_depth, profiles_df); deep_subset = profiles_df[profiles_df['dive_depth_m'] == next_depth].sort_values('bottom_time_min'); target_idx = calculate_profile_index(deep_subset, calculation_time_min, risk_active, is_longer=False); target_profile_id = deep_subset.iloc[target_idx]['profile_id'] if target_idx != -1 else None
            elif selection == "Deeper & Longer": next_depth = get_next_depth(current_table_depth, profiles_df); deep_subset = profiles_df[profiles_df['dive_depth_m'] == next_depth].sort_values('bottom_time_min'); target_idx = calculate_profile_index(deep_subset, calculation_time_min, risk_active, is_longer=True); target_profile_id = deep_subset.iloc[target_idx]['profile_id'] if target_idx != -1 else None

            st.session_state.active_profile_id_tracker = target_profile_id
            st.session_state.current_selection_name = selection 

            is_break_active = False
            if st.session_state.break_phase is not None:
                is_break_active = True
                elapsed_break = current_timestamp - st.session_state.break_start_time
                remaining_break = st.session_state.break_duration - elapsed_break
                if remaining_break <= 0:
                    if st.session_state.break_phase == '5min':
                        st.session_state.break_phase = '10min'; st.session_state.break_duration = 600; st.session_state.break_start_time = current_timestamp; st.rerun()
                    else:
                        st.session_state.break_phase = None; st.session_state.break_start_time = None; st.session_state.break_duration = 0; is_break_active = False
                        if st.session_state.pre_deco_break_occurred and not st.session_state.deco_phase_active:
                            st.session_state.deco_phase_active = True
                            st.session_state.deco_start_time = current_timestamp
                        st.rerun()

            active_profile_steps = []
            
            tick_profile_id = st.session_state.locked_profile_id if is_plan_locked else target_profile_id

            if tick_profile_id is not None:
                stops_main = stops_df[stops_df['profile_id'] == tick_profile_id].sort_values('stop_depth_m', ascending=False)
                row_main = profiles_df[profiles_df['profile_id'] == tick_profile_id].iloc[0]
                active_profile_steps.append({'type': 'ascent', 'depth': 0, 'air_sec': row_main['ascent_to_1st_stop_min'] * 60, 'o2_sec': None})
                for _, stop in stops_main.iterrows():
                    d_air_min = stop['duration_air_min']; d_o2_min = calculate_o2_time(d_air_min, stop['stop_depth_m'])
                    active_profile_steps.append({'type': 'stop', 'depth': stop['stop_depth_m'], 'air_sec': d_air_min * 60, 'o2_sec': d_o2_min * 60 if d_o2_min else None})

            if st.session_state.deco_phase_active and tick_profile_id is not None and active_profile_steps:
                last_tick = st.session_state.deco_last_tick
                if last_tick is None: st.session_state.deco_last_tick = current_timestamp
                else:
                    delta = current_timestamp - last_tick; st.session_state.deco_last_tick = current_timestamp
                    if not is_break_active:
                        curr_idx = st.session_state.deco_step_index
                        if curr_idx < len(active_profile_steps):
                            step_data = active_profile_steps[curr_idx]
                            efficiency = 1.0 
                            if st.session_state.deco_o2_enabled and step_data['o2_sec'] is not None: efficiency = step_data['air_sec'] / step_data['o2_sec']
                            st.session_state.deco_step_progress_air_sec += (delta * efficiency)
                            if st.session_state.deco_step_progress_air_sec >= step_data['air_sec']:
                                st.session_state.deco_step_index += 1
                                st.session_state.deco_step_progress_air_sec = 0.0
                                if st.session_state.deco_step_index >= len(active_profile_steps):
                                    now = time.time(); start_dt = datetime.fromtimestamp(st.session_state.start_time); deco_str = ""
                                    if st.session_state.deco_start_time: deco_str = datetime.fromtimestamp(st.session_state.deco_start_time).strftime("%H:%M")
                                    end_dt = datetime.fromtimestamp(now)
                                    if st.session_state.locked_bottom_time_min > 0 or st.session_state.locked_bottom_time_sec > 0: actual_bot = st.session_state.locked_bottom_time_min + (st.session_state.locked_bottom_time_sec / 60.0)
                                    else: actual_bot = (now - st.session_state.start_time) / 60.0
                                    st.session_state.logbook_context = {"date": start_dt.strftime("%Y-%m-%d"), "start_time": start_dt.strftime("%H:%M"), "depth": st.session_state.planned_depth, "deco_start": deco_str, "end_time": end_dt.strftime("%H:%M"), "final_profile_id": st.session_state.locked_profile_id, "actual_bottom_time_min": actual_bot, "used_o2": st.session_state.deco_o2_enabled, "break_events": st.session_state.break_events, "pre_deco_break": st.session_state.pre_deco_break_occurred}
                                    st.session_state.page = 'logbook'; st.rerun()
            
            if target_profile_id is not None:
                target_row = profiles_df[profiles_df['profile_id'] == target_profile_id].iloc[0]
                
                is_currently_locked = (is_plan_locked and target_profile_id == st.session_state.locked_profile_id)
                
                if is_currently_locked:
                    plan_str = f"<span style='color: #00CC66; font-weight: bold;'>{selection} (AKTYWNY)</span>"
                else:
                    plan_str = selection
                    
                st.markdown(f"**Plan:** {plan_str} | **Profile:** {target_row['dive_depth_m']} / {target_row['bottom_time_min']}", unsafe_allow_html=True)
                
                vis_stops = stops_df[stops_df['profile_id'] == target_profile_id].sort_values('stop_depth_m', ascending=False)
                vis_steps = []
                vis_steps.append({'label_depth': "Ascent to 1st stop", 'label_time': f"{target_row['ascent_to_1st_stop_min']} min", 'air_min': target_row['ascent_to_1st_stop_min'], 'o2_min': None})
                for _, stop in vis_stops.iterrows():
                    d_air = stop['duration_air_min']; d_o2 = calculate_o2_time(d_air, stop['stop_depth_m'])
                    lbl = f"{d_air}({d_o2}) min" if d_o2 else f"{d_air} min"
                    vis_steps.append({'label_depth': f"at {stop['stop_depth_m']} m", 'label_time': lbl, 'air_min': d_air, 'o2_min': d_o2})
                
                cards_html = '<div class="scrolling-wrapper">'
                for i, step in enumerate(vis_steps):
                    is_active = False; is_done = False; is_paused = False
                    
                    if is_currently_locked and st.session_state.deco_phase_active:
                        if i < st.session_state.deco_step_index: is_done = True
                        elif i == st.session_state.deco_step_index: is_active = True; is_paused = is_break_active
                    
                    content_html = f'<div class="card-time">{step["label_time"]}</div><div class="card-depth">{step["label_depth"]}</div>'
                    
                    if is_active:
                        if is_paused: content_html += '<div class="card-paused-text">PAUSED (Break)</div>'
                        else:
                            progress_air = st.session_state.deco_step_progress_air_sec; total_air_sec = step['air_min'] * 60.0; remaining_air_sec = max(0, total_air_sec - progress_air)
                            efficiency = 1.0
                            if st.session_state.deco_o2_enabled and step['o2_min'] is not None: efficiency = (step['air_min'] * 60) / (step['o2_min'] * 60)
                            real_rem = remaining_air_sec / efficiency; rem_min = int(real_rem // 60); rem_sec = int(real_rem % 60)
                            content_html += f'<div class="card-countdown">{rem_min}:{rem_sec:02d}</div>'
                    classes = ["card"]; 
                    if is_done: classes.append("done")
                    if is_active: classes.append("active"); 
                    if is_paused and is_active: classes.append("paused")
                    cards_html += f'<div class="{" ".join(classes)}">{content_html}</div>'
                cards_html += '</div>'; st.markdown(cards_html, unsafe_allow_html=True)
            else:
                if selection == "Current Plan": st.info(f"Dive time is within safety limits. No profile active yet.")
                else: st.warning("Data unavailable or time threshold not reached.")
            
            st.divider()

            st.subheader("Adjust Depth")
            is_depth_locked = is_plan_locked
            col_in, col_btn = st.columns([3, 1])
            with col_in: new_depth = st.number_input("New Depth (m):", value=st.session_state.planned_depth, step=1, key="adjust_depth_input", disabled=is_depth_locked)
            with col_btn: 
                st.write(" "); 
                if st.button("Apply Changes", use_container_width=True, disabled=is_depth_locked): st.session_state.planned_depth = new_depth; st.rerun()

            st.write("") 
            chamber_msg = "Not available"; is_chamber_avail = False; aweigh_msg = "Not Available"; is_aweigh_avail = False
            if target_profile_id is not None:
                target_stops = stops_df[stops_df['profile_id'] == target_profile_id]
                eligible_stops = target_stops[target_stops['can_enter_chamber'] == 1]
                if not eligible_stops.empty: deepest = eligible_stops['stop_depth_m'].max(); chamber_msg = f"Available from {deepest} meters downwards"; is_chamber_avail = True
                if not target_stops.empty:
                    if target_stops['stop_depth_m'].max() > 6: is_aweigh_avail = False; aweigh_msg = "Not Available"
                    else: is_aweigh_avail = True; aweigh_msg = "Available"
                else: is_aweigh_avail = True; aweigh_msg = "Available"
            else: is_aweigh_avail = True; aweigh_msg = "Available"

            col_txt_1, col_status_1, col_t_break, col_empty = st.columns([1.5, 1.5, 1.0, 0.1])
            with col_txt_1: st.markdown("**Decompression inside a decompression chamber**")
            with col_status_1:
                if is_chamber_avail: st.markdown(f'<div class="chamber-status-box">{chamber_msg}</div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="chamber-unavailable-box">{chamber_msg}</div>', unsafe_allow_html=True)
            with col_t_break:
                if st.session_state.break_phase is None:
                    if not st.session_state.get('break_used_in_this_dive', False):
                        if st.button("Start 5' Break"):
                            st.session_state.break_phase = '5min'; st.session_state.break_duration = 300; st.session_state.break_start_time = time.time()
                            st.session_state.deco_o2_enabled = True 
                            st.session_state.break_used_in_this_dive = True
                            
                            if st.session_state.deco_phase_active:
                                st.session_state.break_events.append(st.session_state.deco_step_index)
                            else:
                                if st.session_state.get('debug_manual_mode', False): cm = st.session_state.get('debug_manual_time', 0); cs = 0
                                else: te = int(time.time() - st.session_state.start_time); cm = te // 60; cs = te % 60
                                st.session_state.locked_bottom_time_min = cm; st.session_state.locked_bottom_time_sec = cs
                                st.session_state.pre_deco_break_occurred = True
                                
                                st.session_state.locked_plan_name = st.session_state.current_selection_name
                                st.session_state.locked_profile_id = st.session_state.active_profile_id_tracker
                            st.rerun()
                    else:
                        st.button("Start 5' Break", disabled=True, help="Przerwa została już użyta podczas tego nurkowania.")
                else:
                    elapsed = time.time() - st.session_state.break_start_time; remaining = max(0, st.session_state.break_duration - elapsed)
                    mins = int(remaining // 60); secs = int(remaining % 60)
                    label = f"5 min Break: {mins:02d}:{secs:02d}" if st.session_state.break_phase == '5min' else f"10 min Break: {mins:02d}:{secs:02d}"
                    st.button(label, disabled=True, type="primary")

            col_txt_2, col_status_2, col_dummy = st.columns([1.5, 1.5, 1.0])
            with col_txt_2: st.markdown("**Aweigh diver**")
            with col_status_2:
                style_class = "status-box-green" if is_aweigh_avail else "status-box-red"; st.markdown(f'<div class="{style_class}">{aweigh_msg}</div>', unsafe_allow_html=True)

        live_timer_header()
        
        st.write(""); st.write("")
        col_start_deco, col_end_dive = st.columns([1, 1])
        
        with col_start_deco:
            btn_disabled = (st.session_state.break_phase is not None)
            if not st.session_state.deco_phase_active:
                if st.button("Start Decompression", use_container_width=True, disabled=btn_disabled):
                    if st.session_state.get('debug_manual_mode', False): cm = st.session_state.get('debug_manual_time', 0); cs = 0
                    else: te = int(time.time() - st.session_state.start_time); cm = te // 60; cs = te % 60
                    st.session_state.locked_bottom_time_min = cm; st.session_state.locked_bottom_time_sec = cs
                    st.session_state.deco_start_time = time.time()
                    st.session_state.deco_phase_active = True
                    
                    st.session_state.locked_plan_name = st.session_state.current_selection_name
                    st.session_state.locked_profile_id = st.session_state.active_profile_id_tracker
                    
                    st.rerun()
            else: 
                st.info("Decompression Phase Active")

        with col_end_dive:
            if st.button("End Dive", use_container_width=True):
                now = time.time(); start_dt = datetime.fromtimestamp(st.session_state.start_time); deco_str = ""
                if st.session_state.deco_start_time: deco_str = datetime.fromtimestamp(st.session_state.deco_start_time).strftime("%H:%M")
                end_dt = datetime.fromtimestamp(now)
                
                if st.session_state.locked_bottom_time_min > 0 or st.session_state.locked_bottom_time_sec > 0: 
                    actual_bot = st.session_state.locked_bottom_time_min + (st.session_state.locked_bottom_time_sec / 60.0)
                else:
                    if st.session_state.get('debug_manual_mode', False): actual_bot = float(st.session_state.get('debug_manual_time', 0))
                    else: actual_bot = int(now - st.session_state.start_time) / 60.0
                
                final_id = st.session_state.locked_profile_id if st.session_state.locked_profile_id else st.session_state.active_profile_id_tracker
                
                st.session_state.logbook_context = {
                    "date": start_dt.strftime("%Y-%m-%d"), 
                    "start_time": start_dt.strftime("%H:%M"), 
                    "depth": st.session_state.planned_depth, 
                    "deco_start": deco_str, 
                    "end_time": end_dt.strftime("%H:%M"), 
                    "final_profile_id": final_id, 
                    "actual_bottom_time_min": actual_bot, 
                    "used_o2": st.session_state.deco_o2_enabled, 
                    "break_events": st.session_state.break_events, 
                    "pre_deco_break": st.session_state.pre_deco_break_occurred
                }
                st.session_state.page = 'logbook'; placeholder.empty(); st.rerun()
        
        with st.expander("🛠️ Debug Options"):
            chk_debug = st.checkbox("Enable Manual Time Override", key="debug_manual_mode")
            if chk_debug: st.number_input("Set Elapsed Time (minutes):", min_value=0, value=0, step=1, key="debug_manual_time")

def render_logbook_view(placeholder):
    data = st.session_state.logbook_context
    entries = st.session_state.logbook_entries
    profiles_df, stops_df, p_us, s_us, p_swe, s_swe = load_data()
    
    with placeholder.container():
        st.title("Raport z nurkowania (Logbook)")
        st.markdown("---")
        with st.expander("⚙️ Edytuj dane wykresu (Graph Settings)"):
            c_g1, c_g2 = st.columns(2)
            with c_g1: graph_time = st.number_input("Rzeczywisty czas dna (min)", value=float(data.get('actual_bottom_time_min', 0)), step=1.0)
            with c_g2: graph_o2 = st.checkbox("Użyto tlenu do dekompresji?", value=data.get('used_o2', False))
        
        fig = generate_dive_profile_chart(graph_time, graph_o2, data, profiles_df, stops_df, p_us, s_us, p_swe, s_swe)
        if fig: st.plotly_chart(fig, use_container_width=True)
        else: st.info("No decompression profile data available for graph generation.")
        st.markdown("---")

        with st.form("diver_form"):
            
            final_id_for_form = data.get('final_profile_id')
            if final_id_for_form is not None and not profiles_df.empty:
                table_depth_for_form = profiles_df[profiles_df['profile_id'] == final_id_for_form].iloc[0]['dive_depth_m']
            else:
                table_depth_for_form = data.get('depth', '')

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.text_input("Lp.", value=str(st.session_state.form_lp), disabled=True)
            with c2: st.text_input("Data", value=data.get('date', ''), disabled=True)
            with c3: nazwisko = st.text_input("Nazwisko i imię nurka", key="form_nazwisko")
            with c4: rejon = st.text_input("Rejon nurkowania / głębokość", key="form_rejon")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.text_input("Rozpoczęcie zanurzania", value=data.get('start_time', ''), disabled=True)
            with c2: st.text_input("Osiągnięta głębokość", value=str(table_depth_for_form), disabled=True)
            with c3: st.text_input("Rozpoczęcie wynurzania", value=data.get('deco_start', ''), disabled=True)
            with c4: dzwon = st.text_input("Zamknięcie dzwonu", key="form_dzwon")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.text_input("Zakończenie wynurzania", value=data.get('end_time', ''), disabled=True)
            with c2: czas_woda = st.text_input("Ogólny czas dekompresji w wodzie", key="form_czas_woda")
            with c3: czas_komora = st.text_input("Ogólny czas dekompresji w komorze", key="form_czas_komora")
            with c4: czas_ogolny = st.text_input("Czas ogólny pobytu nurka pod wodą", key="form_czas_ogolny")
            c1, c2, c3 = st.columns(3)
            with c1: czas_komora_pobyt = st.text_input("Czas ogólny pobytu nurka w komorze (pobyt)", key="form_czas_komora_pobyt")
            with c2: czynnik = st.text_input("Czynnik oddechowy", key="form_czynnik")
            with c3: sprzet = st.text_input("Rodzaj sprzętu nurkowego", key="form_sprzet")
            sprawdzenie = st.text_input("Potwierdzenie sprawdzenia sprzętu", key="form_sprawdzenie")
            uwagi = st.text_area("Rodzaj wykonanych prac / Informacje o dezynfekcji", key="form_uwagi")
            c1, c2, c3, c4 = st.columns(4)
            with c1: stan_morza = st.text_input("Stan morza", key="form_stan_morza")
            with c2: temp_wody = st.text_input("Temperatura wody", key="form_temp_wody")
            with c3: temp_pow = st.text_input("Temperatura pow.", key="form_temp_pow")
            with c4: prad = st.text_input("Prąd wody", key="form_prad")
            podpis = st.text_input("Nazwisko i podpis kierownika prac oraz lekarza", key="form_podpis")
            col_add, col_dummy = st.columns([1, 4])
            with col_add: submit_add = st.form_submit_button("Dodaj kolejnego nurka")
        
        if submit_add:
            new_entry = {"lp": st.session_state.form_lp, "data": data.get('date', ''), "nazwisko": nazwisko, "rejon": rejon, "start_zanurzania": data.get('start_time', ''), "glebokosc": table_depth_for_form, "start_wynurzania": data.get('deco_start', ''), "zamkniecie_dzwonu": dzwon, "koniec_wynurzania": data.get('end_time', ''), "czas_deco_woda": czas_woda, "czas_deco_komora": czas_komora, "czas_ogolny": czas_ogolny, "czas_komora_pobyt": czas_komora_pobyt, "czynnik": czynnik, "sprzet": sprzet, "sprawdzenie": sprawdzenie, "uwagi": uwagi, "stan_morza": stan_morza, "temp_wody": temp_wody, "temp_pow": temp_pow, "prad": prad, "podpis": podpis}
            st.session_state.logbook_entries.append(new_entry); st.session_state.form_lp += 1; st.rerun()

        if entries:
            st.markdown("### Dodani nurkowie"); preview_df = pd.DataFrame(entries)[['lp', 'nazwisko', 'czas_ogolny', 'sprzet']]; st.dataframe(preview_df)

        st.markdown("---")
        col_new_dive, col_pdf = st.columns([1, 1])
        with col_new_dive:
            if st.button("New Dive Session (Reset)", type="secondary", use_container_width=True):
                st.session_state.page = 'input'; st.session_state.safety_buffer_active = False; st.session_state.timer_5_start = None; st.session_state.timer_10_start = None; st.session_state.deco_phase_active = False; st.session_state.deco_start_time = None; st.session_state.locked_bottom_time_min = 0; st.session_state.locked_bottom_time_sec = 0; st.session_state.deco_step_index = 0; st.session_state.deco_step_progress_air_sec = 0.0; st.session_state.deco_last_tick = None; st.session_state.deco_o2_enabled = False; st.session_state.break_phase = None; st.session_state.break_start_time = None; st.session_state.break_duration = 0; st.session_state.break_events = []; st.session_state.pre_deco_break_occurred = False; st.session_state.logbook_context = {}; st.session_state.logbook_entries = []; st.session_state.form_lp = 1; st.session_state.active_profile_id_tracker = None
                st.session_state.locked_plan_name = None; st.session_state.locked_profile_id = None
                st.session_state.break_used_in_this_dive = False
                placeholder.empty(); st.rerun()
        with col_pdf:
            if entries:
                pdf_data = create_pdf(entries); st.download_button("Pobierz Raport PDF", pdf_data, "raport_nurkowania.pdf", "application/pdf", use_container_width=True, type="primary")
            else: st.warning("Dodaj przynajmniej jednego nurka aby pobrać PDF.")

def main():
    main_placeholder = st.empty()
    if st.session_state.page == 'input': render_input_view(main_placeholder)
    elif st.session_state.page == 'results': render_results_view(main_placeholder)
    elif st.session_state.page == 'logbook': render_logbook_view(main_placeholder)

if __name__ == "__main__":
    main()