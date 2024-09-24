import shiny
from shiny import App, render, ui, reactive
import pandas as pd
import requests
import io
import os

# replace with your actual API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

app_ui = ui.page_fluid(
    ui.panel_title("Dataset Generator"),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_text("description", "Describe the dataset you want", 
                          placeholder="e.g., health data for a family of 4"),
            ui.input_action_button("generate", "Generate Dataset"),
            ui.output_ui("download_button_ui"),  # Placeholder for conditional download button
            ui.output_ui("summary"),
            ui.output_ui("spinner_ui"),  # Spinner output
            open="open",
            width=350
        ),
        ui.navset_tab(
            ui.nav_panel("Data Table",
                         ui.output_data_frame("dataset_table"),
                         )
        )
    )
)

def server(input, output, session):
    dataset = reactive.Value(None)
    summary_text = reactive.Value("")
    spinner_visible = reactive.Value(False)  # Spinner control

    def preprocess_csv(csv_string: str) -> pd.DataFrame:
        csv_io = io.StringIO(csv_string)
        df = pd.read_csv(csv_io)
        df = df.apply(lambda x: pd.to_numeric(x, errors='ignore'))
        return df

    def generate_summary(df: pd.DataFrame) -> str:
        prompt = f"""Summarize the following dataset:

        Dimensions: {df.shape[0]} rows and {df.shape[1]} columns

        Variables:
        {', '.join(df.columns)}

        Please provide a brief summary of the dataset dimensions and variable definitions. Keep it concise, about 3-4 sentences."""

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that summarizes datasets."},
                    {"role": "user", "content": prompt}
                ]
            }
        )

        if response.status_code == 200:
            content = response.json()
            summary = content['choices'][0]['message']['content']
            return summary
        else:
            return "Error generating summary. Please try again later."

    @reactive.Effect
    @reactive.event(input.generate)
    def _():
        description = input.description()
        if not description:
            return
        
        # Show the spinner
        spinner_visible.set(True)

        prompt = f"Generate a fake dataset with at least two variables as a CSV string based on this description: {description}. Include a header row. Limit to 25 rows of data. Ensure all rows have the same number of columns. Do not include any additional text or explanations."

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that generates fake datasets."},
                    {"role": "user", "content": prompt}
                ]
            }
        )

        if response.status_code == 200:
            content = response.json()
            csv_string = content['choices'][0]['message']['content']

            try:
                df = preprocess_csv(csv_string)
                dataset.set(df)

                # Generate and set summary
                summary = generate_summary(df)
                summary_text.set(summary)

            except Exception as e:
                ui.notification_show(f"Error parsing CSV: {str(e)}", type="error")
        else:
            ui.notification_show("Error generating dataset. Please try again later.", type="error")

        # Hide the spinner after completion
        spinner_visible.set(False)

    @output
    @render.data_frame
    def dataset_table():
        df = dataset.get()
        if df is not None:
            return render.DataGrid(df)

    @output
    @render.ui
    def summary():
        if summary_text.get():
            return ui.div(
                ui.h4("Dataset Summary"),
                ui.p(summary_text.get()),
                {"style": "background-color: #f0f0f0; padding: 10px; border-radius: 5px;"}
            )

    @output
    @render.ui
    def download_button_ui():
        df = dataset.get()
        if df is not None:
            return ui.download_button("download", "Download CSV")

    @session.download(filename="generated_dataset.csv")
    def download():
        df = dataset.get()
        if df is not None:
            return df.to_csv(index=False)

    # Spinner UI
    @output
    @render.ui
    def spinner_ui():
        if spinner_visible.get():
            return ui.div(
                ui.img(src="https://i.gifer.com/ZZ5H.gif", height="50px"),
                {"style": "text-align: center;"}
            )
        return ui.div()

app = App(app_ui, server)