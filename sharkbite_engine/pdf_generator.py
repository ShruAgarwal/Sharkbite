import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from fpdf import FPDF
from fpdf.fonts import FontFace
from sharkbite_engine.utils import is_reap_eligible

# --- Helper functions to create consistent PDF sections ---
headings_style = FontFace(emphasis="BOLD", fill_color=(224, 235, 254))

def add_subsection_header(pdf, title):
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, title, 0, 1, 'L')
    pdf.ln(2)


def write_table_from_df(pdf, df, col_widths=None):
    """
    Renders a pandas DataFrame as a table in the PDF.
    Now accepts an optional `col_widths` dictionary to set specific widths.
    """
    if df.empty:
        pdf.cell(0, 10, "No data available to display in table.", 0, 1)
        return

    # --- Dynamic Column Width Logic ---
    effective_page_width = pdf.w - 2 * pdf.l_margin
    num_cols = len(df.columns)
    
    # If no specific widths are provided, distribute evenly
    if not col_widths:
        default_width = effective_page_width / num_cols
        widths = [default_width] * num_cols
    else:
        # Use provided widths and calculate remaining space for other columns
        specified_width_total = sum(col_widths.values())
        num_unspecified = num_cols - len(col_widths)
        
        if num_unspecified > 0:
            remaining_width = (effective_page_width - specified_width_total) / num_unspecified
        else:
            remaining_width = 0 # All columns have specified widths

        widths = []
        for col_name in df.columns:
            widths.append(col_widths.get(col_name, remaining_width))

    pdf.set_font('Helvetica', '', 9)
    with pdf.table(col_widths=widths, text_align="LEFT", line_height=6) as table:
        header = table.row(style=headings_style)
        for col_name in df.columns:
            header.cell(col_name.replace("_", " "))
        
        for _, row_data in df.iterrows():
            row = table.row()
            for item in row_data:
                try:
                    if isinstance(item, (int, float)):
                        row.cell(f"{item:,.0f}")
                    else:
                        row.cell(str(item))
                except (ValueError, TypeError):
                    row.cell(str(item))
    pdf.set_font('Helvetica', '', 10)

# --- Robust helper function to write bulleted lists from AI ---
def write_ai_bullet_points(pdf, items_list):
    """
    Safely writes a list of strings as bullet points to the PDF,
    handling line breaks for long items correctly.
    """
    pdf.set_font('Helvetica', '', 10)

    # Set indentation for bullet points
    indentation = 8  # Adjust as needed
    bullet_indent = 5 # Indentation for the bullet character itself

    for item in items_list:
        # Move the cursor to the correct position for the bullet
        pdf.set_x(pdf.l_margin + bullet_indent)
        pdf.write(5, "- ") # Add the bullet character
        
        # Calculate the remaining width for the text after the bullet
        available_width = pdf.w - pdf.l_margin - pdf.r_margin - indentation - bullet_indent
        
        # Use multi_cell for the actual bullet point text, with indentation
        pdf.set_x(pdf.l_margin + indentation)
        
        # Encode the text to latin-1, replacing any unsupported characters.
        # This prevents the FPDFException.
        safe_item_text = item.encode('latin-1', 'replace').decode('latin-1')
        
        # Use a proper bullet character
        pdf.multi_cell(available_width, 5, safe_item_text)
        pdf.ln(2) # Add a little space after the list


# --- PDF Class with Header/Footer ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_title = "" # A variable to hold the current page's title

    def set_page_title(self, title):
        self.page_title = title

    def header(self):
        try:
            self.image("assets/logo.png", 10, 8, 23, title="Sharkbite Logo")
        except:
            pass # Silently fail
            
        # Use the dynamic page title
        if self.page_title:
            self.set_font('Helvetica', 'B', 16)
            self.set_text_color(0, 68, 124) # Dark blue color
            self.cell(0, 10, self.page_title, 0, 1, 'C')
        self.ln(12)

    def footer(self):
        self.set_y(-15)  # Position at 1.5 cm from bottom
        self.set_font('Helvetica', 'I', 8)
        # Left-aligned text
        self.cell(0, 10, 'Clean Energy Financial Analysis', 0, 0, 'L')
        
        # Center-aligned page number
        self.set_x((self.w / 2) - 10) # Manually center the page number cell
        self.cell(20, 10, f'Page {self.page_no()}', 0, 0, 'C')


# =============== Page Generation Functions (as per Wireframe) ===============
def create_page1_executive_summary(pdf, form_data, final_results, calc_results):
    pdf.set_page_title("Executive Summary")
    pdf.add_page()
    pdf.ln(6)
    
    # Project Overview Box
    add_subsection_header(pdf, "Project Overview")

    ann_savings = calc_results.get("financials", {})
    summary_data = {
        "Business Name/Address": form_data.get("unified_address_zip", "N/A"),
        "Business Type": form_data.get("unified_business_type", "N/A"),
        "Solar PV System Size": f"{form_data.get('calculator_refined_system_size_kw', 0):.2f} kW",
        "Est. Annual Production": f"{calc_results.get('ac_annual', 0):,.0f} kWh",
        "Total Project CapEx": f"${final_results.get('total_project_cost', 0):,.0f}",
        "Net Cost (after Y1 benefits)": f"${final_results.get('final_net_cost', 0):,.0f}",
        "Est. Annual Savings": f"${ann_savings.get('total_annual_savings'):,.0f}"
    }
    write_table_from_df(pdf, pd.DataFrame(summary_data.items(), columns=["Metric", "Value"]))
    pdf.ln(8)

    add_subsection_header(pdf, "Key Metrics Dashboard")
    # ... (code to create key metrics table as in previous response) ...
    with pdf.table(col_widths=(60, 60, 60), text_align="CENTER") as table:
        header = table.row(style=headings_style)
        header.cell("25-Year ROI (%)")
        header.cell("Payback Period (Years)")
        header.cell("Total Year 1 Benefits")
        
        row = table.row()
        financials = calc_results.get("financials", {})
        roi_25 = financials.get("roi_percent_25_yr", 0)
        payback = financials.get("payback_years", float('inf'))
        
        row.cell(f"{roi_25:.1f}%" if roi_25 != float('inf') else "Immediate")
        row.cell(f"{payback:.1f}" if payback != float('inf') else "Immediate")
        row.cell(f"${final_results.get('total_grant_and_tax_benefits', 0):,.0f}")
    pdf.ln(8)
    
    # REAP Score Breakdown (if applicable)
    add_subsection_header(pdf, "REAP Score Breakdown")

    # Run the definitive eligibility check
    is_eligible, reason = is_reap_eligible(form_data)
    if is_eligible:
        if "final_reap_score_for_dashboard" in st.session_state:
            reap_score = st.session_state.final_reap_score_for_dashboard
            if reap_score and isinstance(reap_score, dict):
                pdf.set_font('Helvetica', '', 11)
                pdf.cell(0, 6, f"Final Estimated Score: {reap_score.get('normalized_score', 'N/A')}/100 (Competitive Threshold: 75+)", 0, 1)
                pdf.ln(2)
                pdf.set_font('Helvetica', 'I', 10)
                for detail in reap_score.get('breakdown', []):
                    pdf.cell(0, 5, f"- {detail}", 0, 1)
            else:
                pdf.cell(0, 6, "REAP score not calculated.", 0, 1)
    else:
        # If NOT eligible, display the clear, informative message.
        pdf.set_font('Helvetica', 'I', 11)
        pdf.multi_cell(0, 5, f"Unfortunately, your project is not eligible for the REAP Grant. Here's why: {reason}")
    

def create_page2_system_design(pdf, form_data, calc_results):
    pdf.set_page_title("System Design & Production")
    pdf.add_page()
    pdf.ln(5)

    # ====> System Specs Table <====
    specs_data = {
        "Inverter AC Size": f"{form_data.get('inverter_size_kw', 'N/A'):.2f} kW",
        "Battery Size": f"{calc_results.get('battery_kwh', 'N/A'):.1f} kWh",
        "Battery Cost": f"${calc_results.get('battery_cost', 0):,.0f}",
        "Self-Consumption Rate": f"{calc_results.get('self_consumption_rate_percent', 0):.1f}%",
        "Grid Independence Rate": f"{calc_results.get('grid_independence_rate_percent', 0):.2f}%",
        "Net Grid Interaction": f"{calc_results.get('net_grid_interaction_kwh', 0):,.0f} kWh/yr"
    }
    specs_df = pd.DataFrame(specs_data.items(), columns=["Component", "Specification"])
    write_table_from_df(pdf, specs_df)
    pdf.ln(5)

    # --- Matplotlib Hourly Energy Flow Chart ---
    add_subsection_header(pdf, "Hourly Production vs. Consumption Chart")
    
    if "hourly_energy_flow_chart_data" in st.session_state:
        chart_df = st.session_state.hourly_energy_flow_chart_data
        try:
            fig, ax = plt.subplots(figsize=(10, 5))

            # Stacked bars for consumption
            ax.bar(chart_df.index, chart_df['Solar to Load'], label='Load Met by Solar', color='#FFD700')
            ax.bar(chart_df.index, chart_df['Battery to Load'], bottom=chart_df['Solar to Load'], label='Load Met by Battery', color='#00BFFF')
            ax.bar(chart_df.index, chart_df['Grid Import'], bottom=chart_df['Solar to Load'] + chart_df['Battery to Load'], label='Load Met by Grid (Import)', color='#DC143C')
            
            # Line for total load
            ax.plot(chart_df.index, chart_df['Total Load'], label='Total Household Load', color='black', linestyle='--', linewidth=2)
            
            # Second Y-axis for solar production
            ax2 = ax.twinx()
            ax2.plot(chart_df.index, chart_df['Total Solar Production (DC)'], label='Total Solar Production', color='orange', linestyle='--', linewidth=2)
            
            # Formatting
            ax.set_xlabel("Hour of the Day")
            ax.set_ylabel("Energy Flow (kWh)")
            ax2.set_ylabel("Solar Production (kWh)")
            ax.set_title("How Energy Needs are Met Throughout a Typical Summer Day")
            
            # Combine legends
            lines, labels = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax2.legend(lines + lines2, labels + labels2, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)
            
            fig.tight_layout()
            
            # Save to buffer and embed
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150)
            img_buffer.seek(0)
            pdf.image(img_buffer, w=190)
            plt.close(fig) # <== IMPORTANT to free memory
            pdf.ln(5)

        except Exception as e:
            pdf.cell(0, 6, f"Error rendering hourly flow chart: {e}", 0, 1)

    # --- Matplotlib Monthly Cash Flow Chart & Data Table ---
    add_subsection_header(pdf, "Monthly Financials (Year 1)")
    
    if "monthly_cash_flow_data" in st.session_state:
        monthly_df = st.session_state.monthly_cash_flow_data
        try:
            fig, ax = plt.subplots(figsize=(10, 5))

            # --- Use a numeric index (0-11) for plotting to avoid categorical data warning ---
            x_pos = np.arange(len(monthly_df.index))

            # Stacked bars for cost components
            ax.bar(x_pos, monthly_df["Cost Avoided by Solar ($)"], label='Cost Avoided by Solar') #monthly_df.index
            ax.bar(x_pos, monthly_df["Cost Avoided by Battery ($)"], bottom=monthly_df["Cost Avoided by Solar ($)"], label='Cost Avoided by Battery')
            ax.bar(x_pos, monthly_df["Remaining Grid Import Cost ($)"], bottom=monthly_df["Cost Avoided by Solar ($)"] + monthly_df["Cost Avoided by Battery ($)"], label='Remaining Grid Cost')
            
            # Line for original bill
            ax.plot(x_pos, monthly_df["Original Bill Cost ($)"], label='Original Bill Cost', color='red', linestyle='--', marker='o')

            # Set the x-axis tick labels to be the month names from the DataFrame index
            ax.set_xticks(x_pos)
            ax.set_xticklabels(monthly_df.index)

            ax.set_ylabel("Amount ($)")
            ax.set_title("Breakdown of Monthly Energy Costs & Savings")
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2)
            ax.grid(axis='y', linestyle=':', alpha=0.7)
            fig.tight_layout()

            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150)
            img_buffer.seek(0)
            pdf.image(img_buffer, w=190)
            plt.close(fig)
            pdf.ln(5)

            # Add the detailed monthly data table
            add_subsection_header(pdf, "Detailed Monthly Data (Year 1)")

            # Round the data for cleaner display in the table
            df_for_table = monthly_df.round(0).astype(int).reset_index().rename(columns={"index": "Month"})
        
            # Define specific width for the "Month" column, let others auto-distribute
            custom_widths = {"Month": 13}
            
            write_table_from_df(pdf, df_for_table, col_widths=custom_widths)
            
        except Exception as e:
            pdf.cell(0, 6, f"Error rendering monthly financials chart: {e}", 0, 1)


def create_ppa_vs_ownership_page(pdf, ppa_results):
    """Adds the PPA comparison page, only if PPA analysis was run."""
    pdf.set_page_title("Bonus: PPA vs. Ownership Analysis")
    pdf.add_page()
    pdf.ln(6)

    # Embed Matplotlib Chart from PPA Screen
    add_subsection_header(pdf, "Cumulative Cost Over 25 Years")
    
    try:
        fig = ppa_results.get("matplotlib_chart_fig")
        if fig:
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            pdf.image(img_buffer, w=190)
            plt.close(fig) # <== Important: close the figure to free up memory
        else:
            raise ValueError("Matplotlib figure not found in PPA results.")
    except Exception as e:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.cell(0, 5, f"Could not render PPA comparison chart. Error: {e}", 0, 1)
        
    pdf.ln(5)
    # Embed Summary Table
    add_subsection_header(pdf, "25-Year Financial Comparison Summary")
    ppa_df = ppa_results.get("summary_df")
    summary_df = ppa_df.reset_index().rename(columns={"index": "Metric"})
    write_table_from_df(pdf, summary_df)


def create_page3_financial_breakdown(pdf, final_results):
    pdf.set_page_title("Financial Breakdown")
    pdf.add_page()
    pdf.ln(6)

    # --- Embed the NEW Matplotlib Waterfall Chart ---
    add_subsection_header(pdf, "Cost Structure: Gross to Net")
    
    waterfall_data = final_results.get("waterfall_chart_data")
    final_net_cost = final_results.get("final_net_cost")

    if waterfall_data and final_net_cost is not None:
        try:
            # Prepare the data for plotting
            labels = list(waterfall_data.keys())
            values = np.array(list(waterfall_data.values()))
            
            # Calculate the cumulative sum to find the bottom of each bar
            cumulative_sum = np.cumsum(values)
            # The bottom of each bar is the cumulative sum of the previous values
            bottoms = np.insert(cumulative_sum[:-1], 0, 0)
            
            # Determine bar colors: green for benefits (negative values), blue for costs (positive)
            colors = ['#2ca02c' if v < 0 else '#1f77b4' for v in values] # Green for decreasing, Blue for increasing
            
            # Create the plot
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot the main bars
            ax.bar(labels, values, bottom=bottoms, color=colors, width=0.6)
            
            # Add the final "Net Cost" total bar
            ax.bar("Final Net Cost", final_net_cost, color='#ff7f0e', width=0.6) # Orange for total

            # Add connector lines
            for i in range(len(cumulative_sum) - 1):
                ax.plot([i, i + 1], [cumulative_sum[i], cumulative_sum[i]], color='gray', linestyle='--')
            # Line from last incentive to final total
            ax.plot([len(labels) - 1, len(labels)], [cumulative_sum[-1], 0], color='gray', linestyle='--')
            
            # Add text labels on top of each bar
            for i, (val, bottom) in enumerate(zip(values, bottoms)):
                y_pos = bottom + val if val > 0 else bottom
                ax.text(i, y_pos, f'${abs(val):,.0f}', ha='center', va='bottom' if val > 0 else 'top', fontsize=9)
            # Text for final total
            ax.text(len(labels), final_net_cost, f'${final_net_cost:,.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
            
            # Formatting
            ax.set_ylabel("Amount ($)")
            ax.set_title("Financial Breakdown: From Gross to Net Cost")
            plt.xticks(rotation=45, ha="right") # Rotate labels for readability
            ax.grid(axis='y', linestyle=':', alpha=0.7)
            
            # Format Y-axis with commas
            ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f'${int(x):,}'))
            fig.tight_layout()
            
            # Save to buffer and embed in PDF
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            pdf.image(img_buffer, w=190)
            plt.close(fig)
        except Exception as e:
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 6, f"Error rendering waterfall chart: {e}", 0, 1)
    else:
        pdf.cell(0, 6, "Waterfall chart data was not available.", 0, 1)

    pdf.ln(5)

    # Incentive Summary Table
    add_subsection_header(pdf, "Incentive Summary Table")
    incentive_data = {
        "REAP Grant (Adjusted)": final_results.get("reap_grant_final", 0),
        "Federal ITC (Total)": final_results.get("total_itc_value", 0),
        "Y1 Depreciation Benefit": final_results.get("year_1_depreciation_tax_benefit", 0),
        **final_results.get("other_grant_values", {})
    }
    incentive_df = pd.DataFrame(incentive_data.items(), columns=["Incentive Program", "Value ($)"])
    write_table_from_df(pdf, incentive_df)


def create_page4_ai_insights(pdf):
    pdf.set_page_title("AI Insights & Recommendations")
    pdf.add_page()
    pdf.ln(6)

    ai_analysis = st.session_state.get("final_ai_analysis")
    if ai_analysis and not ai_analysis.get("error"):
        add_subsection_header(pdf, "Executive Summary from AI")
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 5, ai_analysis.get("executive_summary", "N/A"))
        pdf.ln(5)

        add_subsection_header(pdf, "Key Opportunities")
        write_ai_bullet_points(pdf, ai_analysis.get('key_opportunities', ["N/A"]))
        
        add_subsection_header(pdf, "Primary Risks")
        write_ai_bullet_points(pdf, ai_analysis.get('primary_risks', ["N/A"]))
       
        add_subsection_header(pdf, "Mitigation Strategies")
        write_ai_bullet_points(pdf, ai_analysis.get('mitigation_strategies', ["N/A"]))
    else:
        pdf.set_font('Helvetica', 'I', 11)
        pdf.cell(0, 10, 'AI analysis was not generated for this project!', 0, 1)


# ======= Main PDF Generation Orchestrator =======
def generate_pdf_report():
    """Main orchestrator for creating the full PDF report."""
    form_data = st.session_state.form_data
    final_results = st.session_state.get("final_financial_results")
    calc_results = st.session_state.get("calculator_results_display")

    if not all([form_data, final_results, calc_results]):
        st.error("Cannot generate PDF. Required data is missing.")
        return None

    pdf = PDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    create_page1_executive_summary(pdf, form_data, final_results, calc_results)
    create_page2_system_design(pdf, form_data, calc_results)

    # Conditionally add PPA page if the analysis was run
    if "ppa_results" in st.session_state and st.session_state.ppa_results:
        create_ppa_vs_ownership_page(pdf, st.session_state.ppa_results)

    create_page3_financial_breakdown(pdf, final_results)
    create_page4_ai_insights(pdf)
    
    return bytes(pdf.output())