import streamlit as st
import pandas as pd
import time
import math

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
    min-height: 100px; 
    align-items: center;
}
div.card {
    flex: 0 0 auto;
    background-color: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 15px;
    width: 160px;
    text-align: center;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    justify-content: center;
}
div.card-time {
    font-size: 1.2rem;
    font-weight: bold;
    color: #333;
    margin-bottom: 5px;
}
div.card-depth {
    font-size: 0.9rem;
    color: #666;
    font-weight: 500;
}
div.scrolling-wrapper::-webkit-scrollbar {
    height: 8px;
}
div.scrolling-wrapper::-webkit-scrollbar-thumb {
    background-color: #cccccc;
    border-radius: 4px;
}
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
}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    try:
        profiles = pd.read_csv('dive_profiles.csv')
        stops = pd.read_csv('deco_stops.csv')
        return profiles, stops
    except FileNotFoundError:
        st.error("CSV files not found. Please ensure 'dive_profiles.csv' and 'deco_stops.csv' are in the app folder.")
        return pd.DataFrame(), pd.DataFrame()

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
    """
    Returns the target profile index based on what we are APPROACHING (>=).
    Safety Shift is UNCONDITIONAL (Always +1 if active).
    Longer Shift is UNCONDITIONAL (Always +1 if active).
    """
    if subset.empty: return -1

    valid_times = subset[subset['bottom_time_min'] >= elapsed_min]
    
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

if 'page' not in st.session_state:
    st.session_state.page = 'input'
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'planned_depth' not in st.session_state:
    st.session_state.planned_depth = 0
if 'safety_buffer_active' not in st.session_state:
    st.session_state.safety_buffer_active = False

if 'timer_5_start' not in st.session_state:
    st.session_state.timer_5_start = None
if 'timer_10_start' not in st.session_state:
    st.session_state.timer_10_start = None

if 'deco_phase_active' not in st.session_state:
    st.session_state.deco_phase_active = False
if 'deco_start_time' not in st.session_state:
    st.session_state.deco_start_time = None
if 'locked_bottom_time_min' not in st.session_state:
    st.session_state.locked_bottom_time_min = 0


def render_input_view(placeholder):
    with placeholder.container():
        st.title("🤿 Start New Dive")
        depth_input = st.number_input("Planned Depth (m):", min_value=0, value=15, step=1, key="input_depth")
        st.markdown("### Safety Risk Factors")
        c1, c2 = st.columns(2)
        with c1:
            f1 = st.checkbox("Not trained diver", key="chk_1")
            f2 = st.checkbox("DCS likelihood", key="chk_2")
            f3 = st.checkbox("Doing very hard work", key="chk_3")
        with c2:
            f4 = st.checkbox("Water temperature below 10°C", key="chk_4")
            f5 = st.checkbox("Other non-ideal scenario", key="chk_5")
        
        is_depth_valid = depth_input > 0
        if not is_depth_valid:
            st.warning("⚠️ Please provide a depth value to enable the Start button.")
            
        if st.button("Start Dive", type="primary", disabled=not is_depth_valid):
            st.session_state.safety_buffer_active = any([f1, f2, f3, f4, f5])
            st.session_state.planned_depth = depth_input
            st.session_state.start_time = time.time()
            st.session_state.page = 'results'
            st.session_state.debug_manual_mode = False
            st.session_state.debug_manual_time = 0
            
            st.session_state.timer_5_start = None
            st.session_state.timer_10_start = None
            
            st.session_state.deco_phase_active = False
            st.session_state.deco_start_time = None
            st.session_state.locked_bottom_time_min = 0
            
            placeholder.empty()
            st.rerun()

def render_results_view(placeholder):
    profiles_df, stops_df = load_data()
    with placeholder.container():
        @st.fragment(run_every=1)
        def live_timer_header():
            
            if st.session_state.get('debug_manual_mode', False):
                raw_elapsed_min = st.session_state.get('debug_manual_time', 0)
                raw_elapsed_sec = 0
                is_debug = True
            else:
                elapsed_seconds = int(time.time() - st.session_state.start_time)
                raw_elapsed_min = elapsed_seconds // 60
                raw_elapsed_sec = elapsed_seconds % 60
                is_debug = False
            
            if st.session_state.deco_phase_active:
                calculation_time_min = st.session_state.locked_bottom_time_min
                display_min = st.session_state.locked_bottom_time_min
                display_sec = 0 
                
                deco_seconds_total = int(time.time() - st.session_state.deco_start_time)
                deco_min = deco_seconds_total // 60
                deco_sec = deco_seconds_total % 60
                
                status_text = "BOTTOM TIME (ENDED)"
                timer_color = "#888888" 
            else:
                calculation_time_min = raw_elapsed_min
                display_min = raw_elapsed_min
                display_sec = raw_elapsed_sec
                
                deco_min = 0
                deco_sec = 0
                
                if is_debug:
                    timer_color = "#3399FF"
                    status_text = "MANUAL DEBUG TIME"
                elif st.session_state.safety_buffer_active:
                    timer_color = "#FFA500"
                    status_text = "BOTTOM TIME"
                else:
                    timer_color = "#00CC66"
                    status_text = "BOTTOM TIME"

            user_depth = st.session_state.planned_depth
            risk_active = st.session_state.safety_buffer_active
            current_table_depth = get_safe_table_depth(user_depth, profiles_df)
            current_subset = profiles_df[profiles_df['dive_depth_m'] == current_table_depth].sort_values('bottom_time_min')
            
            idx_current = calculate_profile_index(current_subset, calculation_time_min, risk_active, is_longer=False)
            
            if idx_current != -1:
                row = current_subset.iloc[idx_current]
                current_profile_str = f"{current_table_depth} / {row['bottom_time_min']}"
                
                idx_raw = calculate_profile_index(current_subset, calculation_time_min, risk_active=False, is_longer=False)
                safety_visual = (idx_current > idx_raw)
                current_profile_id = row['profile_id']
            else:
                current_profile_str = "No Data"
                safety_visual = False
                current_profile_id = None

            c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
            with c1:
                st.metric("PLANNED DEPTH", f"{user_depth}m", delta=f"Using Table: {current_table_depth}m" if current_table_depth != user_depth else None, delta_color="off")
            with c2:
                st.markdown(f"<h1 style='text-align: center; color: {timer_color}; margin: 0; padding: 0;'>{display_min:02d}:{display_sec:02d}</h1>", unsafe_allow_html=True)
                st.caption(f"<p style='text-align: center;'>{status_text}</p>", unsafe_allow_html=True)
            with c3:
                if st.session_state.deco_phase_active:
                    st.markdown(f"<h1 style='text-align: center; color: #3399FF; margin: 0; padding: 0;'>{deco_min:02d}:{deco_sec:02d}</h1>", unsafe_allow_html=True)
                    st.caption(f"<p style='text-align: center;'>DECOMPRESSION TIME</p>", unsafe_allow_html=True)
                else:
                    st.markdown("") 
            with c4:
                st.metric("PROFILE", current_profile_str, delta="Safety (+1)" if safety_visual else None)
            
            st.divider()

            st.markdown("### Next Stops Plan")
            scenario_options = ["Current Plan", "Deeper", "Longer", "Deeper & Longer"]
            selection = st.radio("Select Scenario:", scenario_options, index=0, horizontal=True, label_visibility="collapsed")
            
            target_profile_id = None
            target_depth_val = 0
            target_time_val = 0
            ascent_time = 0

            if selection == "Current Plan":
                target_idx = calculate_profile_index(current_subset, calculation_time_min, risk_active, is_longer=False)
                if target_idx != -1: target_profile_id = current_subset.iloc[target_idx]['profile_id']
            
            elif selection == "Longer":
                target_idx = calculate_profile_index(current_subset, calculation_time_min, risk_active, is_longer=True)
                if target_idx != -1: target_profile_id = current_subset.iloc[target_idx]['profile_id']
            
            elif selection == "Deeper":
                next_depth = get_next_depth(current_table_depth, profiles_df)
                deep_subset = profiles_df[profiles_df['dive_depth_m'] == next_depth].sort_values('bottom_time_min')
                target_idx = calculate_profile_index(deep_subset, calculation_time_min, risk_active, is_longer=False)
                if target_idx != -1: target_profile_id = deep_subset.iloc[target_idx]['profile_id']
            
            elif selection == "Deeper & Longer":
                next_depth = get_next_depth(current_table_depth, profiles_df)
                deep_subset = profiles_df[profiles_df['dive_depth_m'] == next_depth].sort_values('bottom_time_min')
                target_idx = calculate_profile_index(deep_subset, calculation_time_min, risk_active, is_longer=True)
                if target_idx != -1: target_profile_id = deep_subset.iloc[target_idx]['profile_id']

            if target_profile_id is not None:
                target_row = profiles_df[profiles_df['profile_id'] == target_profile_id].iloc[0]
                target_depth_val = target_row['dive_depth_m']
                target_time_val = target_row['bottom_time_min']
                ascent_time = target_row['ascent_to_1st_stop_min']

                st.markdown(f"**Plan:** {selection} | **Profile:** {target_depth_val} / {target_time_val}")
                
                my_stops = stops_df[stops_df['profile_id'] == target_profile_id].sort_values('stop_depth_m', ascending=False)
                
                cards_html = '<div class="scrolling-wrapper">'
                
                cards_html += f"""
                <div class="card" style="border-left: 4px solid #00CC66;">
                    <div class="card-time">{ascent_time} min</div>
                    <div class="card-depth">Ascent to 1st stop</div>
                </div>
                """
                
                if not my_stops.empty:
                    for _, stop in my_stops.iterrows():
                        depth = stop['stop_depth_m']
                        air_time = stop['duration_air_min']
                        o2_time = calculate_o2_time(air_time, depth)
                        time_str = f"{air_time}({o2_time}) min" if o2_time is not None else f"{air_time} min"
                        cards_html += f'<div class="card"><div class="card-time">{time_str}</div><div class="card-depth">at {depth} m</div></div>'
                else:
                    pass

                cards_html += '</div>'
                st.markdown(cards_html, unsafe_allow_html=True)
            else:
                if selection == "Current Plan":
                     st.info(f"Dive time is within safety limits. No profile active yet.")
                else:
                     st.warning("Data unavailable or time threshold not reached.")
            
            st.divider()

            st.subheader("Adjust Depth")
            col_in, col_btn = st.columns([3, 1])
            with col_in:
                new_depth = st.number_input("New Depth (m):", value=st.session_state.planned_depth, step=1, key="adjust_depth_input")
            with col_btn:
                st.write(" ")
                if st.button("Apply Changes", use_container_width=True):
                    st.session_state.planned_depth = new_depth
                    st.rerun()

            st.write("") 
            
            chamber_msg = "Not available"
            is_chamber_avail = False
            aweigh_msg = "Not Available"
            is_aweigh_avail = False

            if current_profile_id is not None:
                current_stops = stops_df[stops_df['profile_id'] == current_profile_id]
                eligible_stops = current_stops[current_stops['can_enter_chamber'] == 1]
                if not eligible_stops.empty:
                    deepest_stop = eligible_stops['stop_depth_m'].max()
                    chamber_msg = f"Available from {deepest_stop} meters downwards"
                    is_chamber_avail = True
                
                if not current_stops.empty:
                    max_stop_depth = current_stops['stop_depth_m'].max()
                    if max_stop_depth > 6:
                        is_aweigh_avail = False
                        aweigh_msg = "Not Available"
                    else:
                        is_aweigh_avail = True
                        aweigh_msg = "Available"
                else:
                    is_aweigh_avail = True
                    aweigh_msg = "Available"
            else:
                 is_aweigh_avail = True
                 aweigh_msg = "Available"

            col_txt_1, col_status_1, col_t5, col_t10 = st.columns([1.5, 1.5, 0.5, 0.5])
            
            with col_txt_1:
                st.markdown("**Decompression inside a decompression chamber**")
            with col_status_1:
                if is_chamber_avail:
                    st.markdown(f'<div class="chamber-status-box">{chamber_msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chamber-unavailable-box">{chamber_msg}</div>', unsafe_allow_html=True)
            
            with col_t5:
                if st.session_state.timer_5_start is None:
                    if st.button("Start 5'"):
                        st.session_state.timer_5_start = time.time()
                        st.rerun()
                else:
                    diff = 300 - (time.time() - st.session_state.timer_5_start)
                    if diff > 0:
                        mins = int(diff // 60)
                        secs = int(diff % 60)
                        if st.button(f"{mins:02d}:{secs:02d}", type="primary", help="Click to stop"):
                            st.session_state.timer_5_start = None
                            st.rerun()
                    else:
                        st.session_state.timer_5_start = None
                        st.rerun()

            with col_t10:
                if st.session_state.timer_10_start is None:
                    if st.button("Start 10'"):
                        st.session_state.timer_10_start = time.time()
                        st.rerun()
                else:
                    diff = 600 - (time.time() - st.session_state.timer_10_start)
                    if diff > 0:
                        mins = int(diff // 60)
                        secs = int(diff % 60)
                        if st.button(f"{mins:02d}:{secs:02d}", type="primary", help="Click to stop"):
                            st.session_state.timer_10_start = None
                            st.rerun()
                    else:
                        st.session_state.timer_10_start = None
                        st.rerun()

            st.write("")
            col_txt_2, col_status_2, col_dummy = st.columns([1.5, 1.5, 1.0])
            with col_txt_2:
                st.markdown("**Aweigh diver**")
            with col_status_2:
                style_class = "status-box-green" if is_aweigh_avail else "status-box-red"
                st.markdown(f'<div class="{style_class}">{aweigh_msg}</div>', unsafe_allow_html=True)

        live_timer_header()
        
        st.write("")
        st.write("")
        col_start_deco, col_end_dive = st.columns([1, 1])
        
        with col_start_deco:
            if not st.session_state.deco_phase_active:
                if st.button("Start Decompression", use_container_width=True):
                    if st.session_state.get('debug_manual_mode', False):
                        current_mins = st.session_state.get('debug_manual_time', 0)
                    else:
                        current_secs = int(time.time() - st.session_state.start_time)
                        current_mins = current_secs // 60
                    
                    st.session_state.locked_bottom_time_min = current_mins
                    st.session_state.deco_start_time = time.time()
                    st.session_state.deco_phase_active = True
                    st.rerun()
            else:
                 st.info("Decompression Phase Active")

        with col_end_dive:
            if st.button("End Dive", use_container_width=True):
                st.session_state.page = 'input'
                st.session_state.safety_buffer_active = False
                st.session_state.timer_5_start = None
                st.session_state.timer_10_start = None
                st.session_state.deco_phase_active = False
                st.session_state.deco_start_time = None
                st.session_state.locked_bottom_time_min = 0
                placeholder.empty()
                st.rerun()
        
        with st.expander("🛠️ Debug Options"):
            chk_debug = st.checkbox("Enable Manual Time Override", key="debug_manual_mode")
            if chk_debug:
                st.number_input("Set Elapsed Time (minutes):", min_value=0, value=0, step=1, key="debug_manual_time")

def main():
    main_placeholder = st.empty()
    if st.session_state.page == 'input':
        render_input_view(main_placeholder)
    elif st.session_state.page == 'results':
        render_results_view(main_placeholder)

if __name__ == "__main__":
    main()