Mutual Fund Analytics Project

This is my Day 1 project where I'm learning to work with mutual fund data
(NAV = Net Asset Value, basically the price of one unit of a fund).

I'm using some CSV files I was given, plus live data pulled from a free API
called mfapi.in.

What's in this folder


data/raw — the original CSV files, untouched
data/processed — cleaned up data I made from the raw files
notebooks — Jupyter notebooks where I explore and chart the data
sql — SQL queries (coming later)
dashboard — dashboard stuff (coming later)
reports — summary notes about the data
data_ingestion.py — script that loads all the CSVs and checks them for problems
live_nav_fetch.py — script that downloads live NAV data from the API
requirements.txt — list of Python packages this project needs


How to set it up


Make a virtual environment (keeps this project's packages separate from everything else):


cmd   python -m venv venv
   venv\Scripts\activate


Install the packages:


cmd   pip install -r requirements.txt

How to run it


Put the 10 given CSV files into data/raw.
Run this to download live NAV data:


cmd   python live_nav_fetch.py


Run this to check everything and look for problems in the data:


cmd   python data_ingestion.py


Open notebooks/01_eda.ipynb in VS Code to see charts of the NAV data.


Things I learned / got stuck on


Make sure VS Code is using my venv for the notebook, not some other Python (like Anaconda). If I get weird errors about missing packages, this is usually why.
After installing a new package, I have to restart the kernel in the notebook — just re-running the cell isn't enough.
AMFI fund codes can sometimes point to a different fund than expected, so I added a check that warns me if the name doesn't match what I expected.
