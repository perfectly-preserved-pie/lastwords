# Publishing Texas' death row inmates' last statements before execution to a Tumblr blog
# A fun wholesome project written by Sahib Bhai during the Holiday Season 2021 🎅🎄
# https://github.com/perfectly-preserved-pie/lastwords

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
# https://stackoverflow.com/a/43399866
df = df[~df["Last Statement"].isin(['This inmate declined to make a last statement.','No statement was made.','No statement given.','None','(Written statement)','Spoken: No','Spoken: No.','No','No last statement.'])]
# Clean up rows with empty cells
# https://www.w3schools.com/python/pandas/pandas_cleaning_empty_cells.asp
df.dropna(inplace = True)

# Sort the df by oldest executions first
# https://stackoverflow.com/a/67689015
# https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html
df_datesorted = df.sort_values(by="Date", key=pd.to_datetime, ascending=True)

# Iterate over each inmate in the dataframe and use .loc to select specific rows
# https://towardsdatascience.com/how-to-use-loc-and-iloc-for-selecting-data-in-pandas-bd09cb4c3d79
# Also, we're gonna hit Tumblr's API limits as it stands: 
#    1. 250 posts/day.
#    2. Can only have 300 posts in the queue at once.
# We have 573 inmates in the df. Publishing 200 of them brings the remainder down to 323, which means we're just 23 over the max queue limit. Annoying!
# My shitty solution is to publish the first 250 executions (from the total index to total index minus 250) on day 1, then wait 24 hours, then publish the next 23, bringing the remainder to 300 and having that 300 be queued.
# If there are 250 or less posts, we're good to use the API
if (len(df_datesorted.loc[(len(df_datesorted.index)):(len(df_datesorted.index))-250])) <= 250:
    for inmate in df_datesorted.loc[(len(df_datesorted.index)):(len(df_datesorted.index))-250].itertuples():
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
        client.create_quote('lastwords2', state="published", quote=quote, source=source, tags=[tags]) 
else:
    print("The number of posts is too high. No API call will be sent.")

# Wait 24 hours until our post API limit resets    
time.sleep(86400)

# Post the next 23 posts
# we're expecting 23 posts, so add an if check
if (len(df_datesorted.loc[(len(df_datesorted.index))-251:300])) == 23:
    for inmate in df_datesorted.loc[(len(df_datesorted.index))-251:300].itertuples():
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
        client.create_quote('lastwords2', state="published", quote=quote, source=source, tags=[tags]) 
else:
    print("The number of expected posts was NOT 23. No API call will be sent.")

# Queue the remaining posts from index 299 to the last index (should be 300 rows)
if (len(df_datesorted.loc[299:0])) <= 300:
    for inmate in df_datesorted.loc[299:0].itertuples():
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
else:
    print("The number of queued expected posts was not less than 300. No API call will be sent.")