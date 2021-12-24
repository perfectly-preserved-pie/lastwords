import random
import time
import csv

import pandas as pd
import requests
from lxml import html

# Tumblr API stuff
# This needs to be done first manually: https://github.com/tumblr/pytumblr/blob/master/interactive_console.py

# TDCJ stuff
base_url = "https://www.tdcj.texas.gov/death_row"
response = requests.get(f"{base_url}/dr_executed_offenders.html", verify=False)
statement_xpath = '//*[@id="content_right"]/p[6]/text()'


def clean(first_and_last_name: list) -> str:
    name = "".join(first_and_last_name).replace(" ", "").lower()
    return name.replace(", Jr.", "").replace(", Sr.", "").replace("'", "")


def get_last_statement(statement_url: str) -> str:
    page = requests.get(statement_url, verify=False).text
    statement = html.fromstring(page).xpath(statement_xpath)
    text = next(iter(statement), "")
    return " ".join(text.split())


df = pd.read_html(response.content, flavor="bs4")
df = pd.concat(df)

df.rename(
    columns={'Link': "Offender Information", "Link.1": "Last Statement URL"},
    inplace=True,
)

df["Offender Information"] = df[
    ["Last Name", 'First Name']
].apply(lambda x: f"{base_url}/dr_info/{clean(x)}.html", axis=1)

df["Last Statement URL"] = df[
    ["Last Name", 'First Name']
].apply(lambda x: f"{base_url}/dr_info/{clean(x)}last.html", axis=1)

offender_data = list(
    zip(
        df["First Name"],
        df["Last Name"],
        df["Last Statement URL"],
    )
)

statements = []
for item in offender_data:
    *names, url = item
    print(f"Fetching statement for {' '.join(names)}...")
    statements.append(get_last_statement(statement_url=url))
    time.sleep(random.randint(1, 4))

df["Last Statement"] = statements
# Export to CSV using the utf-8-sig encoding
# https://stackoverflow.com/a/43684587
df.to_csv("offenders_data_utf8.csv", index=False, encoding="utf-8-sig")

# Use Pandas to put all this crap into a dataframe
dfcsv = pd.read_csv('/mnt/c/Users/lunar/Documents/offenders_data_utf8.csv')
# Iterate over the dataframe and send one API call every day
for inmate in dfcsv.head().itertuples():
    	client.create_quote('lastwords2', state="queued", quote="print(inmate[11])", source="print(f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>")"