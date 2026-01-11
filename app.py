import gradio as gr
import pandas as pd
from datetime import datetime
from typing import Optional, List
import sqlite3
import json

from src.spacex_tracker import SpaceXTracker

class SpaceXGradioApp:
    def __init__(self):
        self.tracker = SpaceXTracker()

        #Initialize data on start
        self.tracker.fetch_launches()

    def get_last_updated_text(self):
        ts = self.tracker.get_cache_last_updated("launches")
        if ts:
            return f"**Last Updated:** {ts}"
        else:
            return "**Last Updated:** No cached data yet"
    
    def get_all_launches_df(self) -> pd.DataFrame:
        """Get all launches as a pandas DataFrame """
        conn = sqlite3.connect(self.tracker.db_path)
        query = """
            SELECT 
                name,
                date_utc,
                CASE 
                    WHEN success = 1 THEN 'Success'
                    WHEN success = 0 THEN 'Failed'
                    ELSE 'Pending'
                END as status,
                rocket_name,
                launchpad_name,
                details
            FROM launches
            ORDER BY date_unix DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # verification required as UTC already available
        df['date_utc'] = pd.to_datetime(df['date_utc']).dt.strftime('%Y-%m-%d %H:%M UTC')
        df.columns = ['Mission Name', 'Launch Date', 'Status', 'Rocket', 'Launch Site', 'Details']
        
        return df
    
    def filter_launches(self, 
                       start_date: Optional[str],
                       end_date: Optional[str],
                       rocket: Optional[str],
                       status: Optional[str],
                       launch_site: Optional[str]) -> pd.DataFrame:
        """Filter launches based on UI filters."""
        conn = sqlite3.connect(self.tracker.db_path)
        
        # Stich query conditions together
        conditions = []
        params = []
        
        if start_date:
            conditions.append("date_unix >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("date_unix <= ?")
            params.append(end_date)
        
        if rocket and rocket != "All":
            conditions.append("rocket_name = ?")
            params.append(rocket)
        
        if status and status != "All":
            if status == "Success":
                conditions.append("success = 1")
            elif status == "Failed":
                conditions.append("success = 0")
            elif status == "Pending":
                conditions.append("success IS NULL")
        
        if launch_site and launch_site != "All":
            conditions.append("launchpad_name = ?")
            params.append(launch_site)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT 
                name,
                date_utc,
                CASE 
                    WHEN success = 1 THEN 'Success'
                    WHEN success = 0 THEN 'Failed'
                    ELSE 'Pending'
                END as status,
                rocket_name,
                launchpad_name,
                details
            FROM launches
            WHERE {where_clause}
            ORDER BY date_unix DESC
        """
        # print("DEBUG: Query template:")
        # print(query)
        # print("DEBUG: Parameters:", params)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame(columns=['Mission Name', 'Launch Date', 'Status', 'Rocket', 'Launch Site', 'Details'])
        
        # verify required as UTC already available
        df['date_utc'] = pd.to_datetime(df['date_utc']).dt.strftime('%Y-%m-%d %H:%M UTC')
        df.columns = ['Mission Name', 'Launch Date', 'Status', 'Rocket', 'Launch Site', 'Details']
        
        return df
    
    def get_filter_options(self):
        """Get unique values for filter dropdowns."""
        conn = sqlite3.connect(self.tracker.db_path)
        cursor = conn.cursor()
        
        # Get unique rockets from DB
        cursor.execute("SELECT DISTINCT rocket_name FROM launches WHERE rocket_name IS NOT NULL ORDER BY rocket_name")
        rockets = ["All"] + [row[0] for row in cursor.fetchall()]
        
        # Get unique launch sites from DB
        cursor.execute("SELECT DISTINCT launchpad_name FROM launches WHERE launchpad_name IS NOT NULL ORDER BY launchpad_name")
        sites = ["All"] + [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return rockets, sites
    
    def get_statistics_summary(self) -> str:
        """Get formatted statistics summary."""
        stats = self.tracker.get_launch_statistics()
        
        summary = (
            f"# SpaceX Launch Statistics\n\n"
            f"## Overall Performance\n\n"
            f"- **Total Launches:** {stats['total']}\n"
            f"- **Successful:** {stats['successful']} ({stats['success_rate']}%)\n"
            f"- **Failed:** {stats['failed']}\n"
            f"- **Pending/Unknown:** {stats['pending']}\n\n"
            f"## Most Used Rockets\n\n"
            f"{''.join(f"- **{rocket}:** {count} launches\n" for rocket, count in stats['by_rocket'])}"
        )
        
        return summary
    
    def get_statistics_charts_data(self):
        stats = self.tracker.get_launch_statistics()

        # ---- Rocket launches stats (success, failed, pending) ----
        rocket_rows = []
        for rocket, data in stats.get("by_rocket_success", {}).items():
            rocket_rows.append({
                "Rocket": rocket,
                "Successful": data.get("successful", 0),
                "Failed": data.get("failed", 0),
                "Pending": data.get("pending", 0)
            })

        # Sort by total launches (successful + failed + pending)
        if rocket_rows:
            rocket_df = pd.DataFrame(rocket_rows)
            rocket_df['Total'] = rocket_df['Successful'] + rocket_df['Failed'] + rocket_df['Pending']
            rocket_df = rocket_df.sort_values("Total", ascending=False).head(10)
            # Drop the Total column as it's not needed for plotting
            rocket_df = rocket_df.drop(columns=['Total'])
            
            # Melt for stacked bar chart
            rocket_df = rocket_df.melt(
                id_vars=['Rocket'],
                value_vars=['Successful', 'Failed', 'Pending'],
                var_name='Status',
                value_name='Count'
            )
        else:
            rocket_df = pd.DataFrame(columns=["Rocket", "Status", "Count"])

        # Launch sites stats
        site_data = stats.get("by_launch_site", {})
        if site_data:
            site_df = pd.DataFrame([
                {"Launch Site": k, "Total Launches": v}
                for k, v in site_data.items()
            ]).sort_values("Total Launches", ascending=False).head(10)
        else:
            site_df = pd.DataFrame(columns=["Launch Site", "Total Launches"])

        #  Frequency data by month/year
        yearly_data = stats.get("by_year", [])
        monthly_data = stats.get("by_month", [])

        # Create separate dataframes with type identifier
        yearly_df = pd.DataFrame(yearly_data, columns=["Period", "Frequency"])
        yearly_df["Type"] = "Yearly"

        monthly_df = pd.DataFrame(monthly_data, columns=["Period", "Frequency"])
        monthly_df["Type"] = "Monthly"

        # Concatenate both dfs
        if not yearly_df.empty or not monthly_df.empty:
            freq_df = pd.concat([yearly_df, monthly_df], ignore_index=True)
        else:
            freq_df = pd.DataFrame(columns=["Period", "Frequency", "Type"])

        # Sort by period for consistent display
        freq_df = freq_df.sort_values("Period").reset_index(drop=True)
        # # Export frequency dataframe to CSV
        # freq_df.to_csv('frequency_data.csv', index=False)
        return rocket_df, site_df, freq_df
    
    def refresh_data(self) -> str:
        """Fetch recent data from API."""
        success = self.tracker.fetch_launches(force_refresh=True)
        if success:
            return "✓ Data refreshed successfully!"
        else:
            return "⚠ Refresh failed, using cached data"


def create_app():
    """Create and configure the Gradio app."""
    app = SpaceXGradioApp()
    rockets, sites = app.get_filter_options()
    
    with gr.Blocks(title="SpaceX Launch Tracker", theme=gr.themes.Soft()) as demo:
        with gr.Row():
            gr.Image(
                r"images\image.jpg",
                show_label=False,
                show_download_button=False
            )
            gr.Markdown("# SpaceX Launch Tracker \n" 
            "Track and analyze SpaceX launches with real-time data from the SpaceX API")

            gr.Markdown("")  # Spacer
            with gr.Column(scale=0, min_width=200):
                refresh_btn_global = gr.Button("🔄 Fetch Data", size="sm", variant="secondary")
                refresh_status_global = gr.Markdown()
    
        with gr.Tabs():
            # Tab 1: Launch Tracking
            with gr.Tab(" Launch Tracking"):
                gr.Markdown("### Filter and explore SpaceX launches")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("#### Filters")
                        start_date = gr.DateTime(
                            label="Start Date",
                            include_time=False,
                            info="Select start date for filtering"
                        )
                        end_date = gr.DateTime(
                            label="End Date",
                            include_time=False,
                            info="Select end date for filtering"
                        )
                        rocket_filter = gr.Dropdown(
                            choices=rockets,
                            value="All",
                            label="Rocket"
                        )
                        status_filter = gr.Dropdown(
                            choices=["All", "Success", "Failed", "Pending"],
                            value="All",
                            label="Status"
                        )
                        launch_site_filter = gr.Dropdown(
                            choices=sites,
                            value="All",
                            label="Launch Site"
                        )
                        
                        with gr.Row():
                            filter_btn = gr.Button("Apply Filters", variant="primary")
                            clear_btn = gr.Button("Clear Filters")
                    
                    with gr.Column(scale=3):
                        launches_table = gr.Dataframe(
                            value=app.get_all_launches_df(),
                            label="Launch Data",
                            wrap=True,
                            interactive=False,
                            column_widths=[
                                120,   # launch_id
                                180,   # mission_name
                                140,   # launch_date
                                160,   # rocket
                                220,   # launch_site
                                300,   # description
                                120    # status
                            ]
                        )
                        
                        result_count = gr.Markdown()
                
                # Filter button on click action
                def apply_filters(start, end, rocket, status, site):
                    # Gradio gives Unix seconds (float)
                    if start is not None:
                        start = int(start)

                    if end is not None:
                        end = int(end)

                    print("DEBUG start unix:", start, type(start))
                    print("DEBUG end unix:", end, type(end))

                    df = app.filter_launches(start, end, rocket, status, site)
                    count_msg = f"**Showing {len(df)} launches**"
                    return df, count_msg
                
                filter_btn.click(
                    fn=apply_filters,
                    inputs=[start_date, end_date, rocket_filter, status_filter, launch_site_filter],
                    outputs=[launches_table, result_count]
                )
                
                # Clear button on click action
                def clear_filters():
                    df = app.get_all_launches_df()
                    return "", "", "All", "All", "All", df, f"**Showing {len(df)} launches**"
                
                clear_btn.click(
                    fn=clear_filters,
                    outputs=[start_date, end_date, rocket_filter, status_filter, launch_site_filter, launches_table, result_count]
                )
            
            # 2nd Tab: Statistics
            with gr.Tab("📊 Statistics"):
                # refresh_btn = gr.Button("🔄 Refresh Data from API", variant="secondary")
                # refresh_status = gr.Markdown()
                
                stats_summary = gr.Markdown(value=app.get_statistics_summary())
                
                gr.Markdown("### Visual Analytics")
                
                with gr.Row():
                    with gr.Column():
                        rocket_success_chart = gr.BarPlot(
                            value=app.get_statistics_charts_data()[0],
                            x="Rocket",
                            y="Count",
                            color="Status",  # ( Stacked by status)
                            title="Launch Status by Rocket",
                            y_title="Number of Launches",
                            color_map={"Successful": "green", "Failed": "red", "Pending": "orange"},
                            height=300
                        )

                        site_chart = gr.BarPlot(
                            value=app.get_statistics_charts_data()[1],
                            x="Launch Site",
                            y="Total Launches",
                            title="Total Launches by Site",
                            height=300
                        )

                with gr.Row():
                    frequency_toggle = gr.Radio(
                        ["Yearly", "Monthly"],
                        value="Yearly",
                        label="Launch Frequency View",
                        interactive=True
                    )

                def update_frequency_chart(view):
                    _, _, freq_df = app.get_statistics_charts_data()
                    # print("DEBUG: Updating frequency df for view:", view)
                    # print("DEBUG: Full df:\n", freq_df)
                    filtered_df = freq_df[freq_df["Type"] == view]
                    # print("DEBUG: Filtered df:\n", filtered_df)
                    filtered_df = filtered_df.drop(columns=["Type"])
                    return filtered_df

                with gr.Row():
                    frequency_chart = gr.BarPlot(
                        value=update_frequency_chart("Yearly"), 
                        x="Period",
                        y="Frequency",
                        title="Launch Frequency",
                        height=450,
                        x_label_angle=-45,
                        y_lim=[0, None]
                    )
                    frequency_toggle.change(
                        fn=update_frequency_chart,
                        inputs=frequency_toggle,
                        outputs=frequency_chart
                    )
        last_updated_md = gr.Markdown(value=app.get_last_updated_text())



        gr.Markdown("""
        ---
        **Data Source:** [SpaceX API](https://github.com/r-spacex/SpaceX-API) | 
        **Cache Duration:** 24 hours
        """)


        
        # Refresh button functionality common for both tabs
        def refresh_all():
            status = app.refresh_data()
            summary = app.get_statistics_summary()
            rocket_df, site_df, freq_df = app.get_statistics_charts_data()
            last_updated = app.get_last_updated_text()

            return status, summary, freq_df, site_df, rocket_df, last_updated
        
        refresh_btn_global.click(
            fn=refresh_all,
            outputs=[
                refresh_status_global,
                stats_summary,
                frequency_chart,
                site_chart,
                rocket_success_chart,
                last_updated_md
            ]
        )
                


        
    return demo


if __name__ == "__main__":
    demo = create_app()
    demo.launch(share=False, server_port=7860)