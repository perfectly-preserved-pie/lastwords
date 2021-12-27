import random
import time
import pytumblr
import pandas as pd
import requests
from lxml import html

# Tumblr API stuff
# This needs to be done first manually: https://github.com/tumblr/pytumblr/blob/master/interactive_console.py
# Create the PyTumblr client
# Read these values from ~/.tumblr (which should've been created with interactive_console.py already)
# https://github.com/tumblr/pytumblr#create-a-client

# Prompt user for the secrets
consumer_key = input("Please enter the consumer key:\n")
consumer_secret = input("Please enter the consumer secret:\n")
oauth_token = input("Please enter the OAuth token:\n")
oauth_secret = input("Please enter the OAuth secret:\n")

client = pytumblr.TumblrRestClient(
    f"{consumer_key}",
    f"{consumer_secret}",
    f"{oauth_token}",
    f"{oauth_secret}",
)

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
# Remove all inmates that don't have a last statement
# https://www.statology.org/pandas-drop-rows-that-contain-string/
df[df["Last Statement"].str.contains("This inmate declined to make a last statement.")==False]
df[df["Last Statement"].str.contains("No statement was made.")==False]
df[df["Last Statement"].str.contains("No statement given.")==False]

# Iterate over each inmate in the dataframe
for inmate in df.head().itertuples():
    # Generate the last statement for each inmate
    quote = inmate[11]
    # Generate the rest of the "source" information
    # use an f-string to assign output to the 'source' variable
    # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
    # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
    source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
    # Generate the tags 
    tags = f"Execution #{inmate.Execution}"
    # Send the API call (the post will be queued)  
    client.create_quote('lastwords2', state="queue", quote=quote, source=source, tags=[tags])  