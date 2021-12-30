# Publishing Texas' death row inmates' last statements before execution to a Tumblr blog
# A fun wholesome project written by Sahib Bhai during the Holiday Season 2021 🎅🎄
# https://github.com/perfectly-preserved-pie/lastwords

from os import replace
import random
import time
import pytumblr
import pandas as pd
import requests
from lxml import html
# Suppress SSL verification warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



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
# this is a slightly modified version of the code I've shamelessly stolen from StackOverflow
# https://stackoverflow.com/a/64873079
# thank you, internet
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

# Create a function to test if the offender statement is an HTML page or JPG image 
# Because some offenders' information is uploaded as a JPG scan and not an HTML page
# if we get a 404, we can assume the URL needs to be rewritten to end in .jpg instead of .html
def check(url):
    header = requests.head(url, verify=False)
    if header.status_code == 404:
        url = url.replace(".html", ".jpg")
        return f"{url}"
    elif header.status_code == 200: # return the unmodified URL if the test was successful
        return f"{url}"

df = pd.read_html(response.content, flavor="bs4")
df = pd.concat(df)

df.rename(
    columns={'Link': "Offender Information", "Link.1": "Last Statement URL"},
    inplace=True,
)

df["Offender Information"] = df[
    ["Last Name", 'First Name']
].apply(lambda x: f"{base_url}/dr_info/{clean(x)}.html", axis=1)

# Apply our previously created function to the Pandas column to rewrite the URL to .jpg if needed
# https://stackoverflow.com/a/54145945
print("Checking Offender Information URLs and rewriting if necessary...")
df["Offender Information"] = df["Offender Information"].apply(check)

print("Cleaning up Last Statement URLs...")
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

df["Last Statement"] = statements

# Remove all inmates that don't have a last statement
# We'll first create a list of keywords indicating no last statement to be rewritten as NaN
# https://stackoverflow.com/a/43399866
print("Removing all inmates without a last statement...")
keywords = ['This inmate declined to make a last statement.','No statement was made.','No statement given.','None','(Written statement)','Spoken: No','Spoken: No.','No','No last statement.','No, I have no final statement.']
df = df[~df['Last Statement'].isin(keywords)]
# Now we drop all rows containing NaN
# https://hackersandslackers.com/pandas-dataframe-drop/
df.dropna(axis=0,how='any',inplace=True)

# Reindex the dataframe so the rows are sequential again
df.reset_index(drop=True, inplace=True)

# Sort the df by oldest executions first
# https://stackoverflow.com/a/67689015
# https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html
print("Sorting dataframe by oldest execution first...")
df.sort_values(by="Date", key=pd.to_datetime, ascending=True, inplace=True)

# Iterate over each inmate in the dataframe and use .loc to select specific rows
# https://towardsdatascience.com/how-to-use-loc-and-iloc-for-selecting-data-in-pandas-bd09cb4c3d79
# Also, we're gonna hit Tumblr's API limits as it stands: 
#    1. Can only post 250 posts/day to either the queue or published
#    2. Can only have 300 posts in the queue at once.
# We have 403 inmates in the df. Publishing 103 immediately brings the remainder down to 300. We can then queue the remaining 300
# My shitty solution is to publish the first 103 oldest executions on day 1, then wait 24 hours, then queue the remaining 300
# If there are 250 or less posts, we're good to use the API
if (len(df.loc[0:103])) <= 250:
    for inmate in df.loc[0:103].itertuples():
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = f"Execution #{inmate.Execution}", f"Index {inmate.Index}"
        # Send the API call (the post will be queued) 
        print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        client.create_quote('lastwords2', state="published", quote=quote, source=source, tags=tags) 
else:
    print("The number of posts is too high. No API call will be sent.")

# Wait 24 hours until our post API limit resets
print("Sleeping for 24 hours...")    
time.sleep(86400)

# Queue the remaining 300 posts
# we're expecting 300 posts, so add an if check
if (len(df.loc[104:df.last_valid_index()])) == 300:
    for inmate in df.loc[104:df.last_valid_index()].itertuples():
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = f"Execution #{inmate.Execution}", f"Index {inmate.Index}"
        # Send the API call (the post will be queued)  
        client.create_quote('lastwords2', state="queue", quote=quote, source=source, tags=tags) 
else:
    print("The number of expected posts was NOT 300. No API call will be sent.")