# 🦈 Sharkbite MVP - Clean Energy Incentive Calculator
 *Take a bite out of high electric bills!*

<!---
# Sharkbite MVP - Clean Energy Incentive Calculator

This project is a Streamlit-based Minimum Viable Product (MVP) for the Sharkbite platform, designed to help users assess eligibility and estimate benefits for clean energy project incentives, with an initial focus on the USDA REAP grant.
--->

## ⚙ Setup and Running the Application
Follow these steps to get the Sharkbite MVP running on your local machine!

**⚡ Prerequisites**
*   Git installed on your system.
*   Miniconda or Anaconda installed on your system.

### 1. Clone the Repository
Open your git bash and run the following command to clone the project files:
```bash
git clone https://github.com/ShruAgarwal/Sharkbite.git
```

### 2. Create and Activate Conda Environment
It is generally recommended to use a Conda environment so as to manage project dependencies and ensure compatibility.

- Open up the Conda terminal and create a new Conda environment named `sharkbite_env` (or your preferred name) with `Python 3.11` (within the main repo):
```bash
conda create -n sharkbite_env python=3.11
```

- Activate the newly created environment:
```bash
conda activate sharkbite_env
```

### 3. Install Dependencies
The necessary Python packages are listed in the `requirements.txt` file. Install them using pip:
```bash
pip install -r requirements.txt
```

### 4. Configure NREL PVWatts API Key
<!--This application uses the NREL PVWatts API to estimate solar energy production which requires an API key from NREL.-->
Add your NREL PVWatts API key to this `secrets.toml` file as follows:
```toml
  # .streamlit/secrets.toml
  NREL_API_KEY = "YOUR_API_KEY_HERE"
```
> 📌 Replace `"YOUR_API_KEY_HERE"` with the API key provided to you. **Do not commit this file with your actual key to a public repository.**

### 5. Run the Streamlit App
Once the environment is set up and the API key is configured, run the following command in your terminal:
```bash
streamlit run sharkbite_app.py
```

This will start the Streamlit development server, and the application should open automatically in your default web browser. If not, the terminal will provide a `local URL: http://localhost:8501` that you can open manually.

<!--
## 📁 Project Structure

Sharkbite/
├── .streamlit/
│   └── config.toml          # Main App Theme
│   └── secrets.toml         # For API keys and other secrets
├── sharkbite_engine/        # Core logic and utilities
│   ├── utils.py             # Calculation functions, API calls, constants
│   └── ui_screens.py        # Streamlit screen rendering functions
├── sharkbite_app.py         # Main Streamlit app
├── requirements.txt         # Project dependencies
├── sk_logo.png              # Main App logo
├── .gitignore               # Files/dependencies to ignore
└── README.md                # About the project & general instructions-->
