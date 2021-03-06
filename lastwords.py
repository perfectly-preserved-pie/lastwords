# Publishing Texas' death row inmates' last statements before execution to a Tumblr blog
# A fun wholesome project written by Sahib Bhai during the Holiday Season 2021 🎅🎄
# https://github.com/perfectly-preserved-pie/lastwords

# Set matplotlib backend to Agg (writing to file)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from os import replace
import random
from bs4 import BeautifulSoup as bs4
import time
import pytumblr
from imgurpython import ImgurClient
import pandas as pd
import numpy as np
import requests
from lxml import html
import lxml
# Suppress SSL verification warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from sympy.solvers import solve
from sympy import Symbol
import csv

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

tumblr_client = pytumblr.TumblrRestClient(
    f"{consumer_key}",
    f"{consumer_secret}",
    f"{oauth_token}",
    f"{oauth_secret}",
)

# Imgur API stuff for hosting the plot graphs
# https://github.com/Imgur/imgurpython#library-usage
client_id = input("Please enter your Imgur client ID:\n")
client_secret = input("Please enter your Imgur client secret:\n")

imgur_client = ImgurClient(
    f"{client_id}",
    f"{client_secret}",
)

# TDCJ stuff
# this is a heavily bastardized version of some code I've shamelessly stolen from StackOverflow
# https://stackoverflow.com/a/64873079
# thank you, internet
base_url = "https://www.tdcj.texas.gov/death_row"
response = requests.get(f"{base_url}/dr_executed_offenders.html", verify=False)

# Create a function to get the last statement text using BeautifulSoup
def get_last_statement(statement_url: str) -> str:
	response = requests.get(statement_url, stream=True, verify=False)
	soup = bs4(response.text, 'html.parser')
	# Find all <p> tags starting at the 5th <p> and ending at some high number (in case of additional paragraphs)
	statement_paragraphs = soup.findAll('p')[5:15]
	statement = []
	# Iterate over the list and get only the text (strip the HTML tags) then append it to statement
	for p in statement_paragraphs:
		# https://stackoverflow.com/a/2077944
		statement.append(' '.join(p.get_text().split()))
	# Join each element into a string
    # https://stackoverflow.com/a/12453584
	return ' '.join(statement)

df = pd.read_html(response.content, flavor="bs4")
df = pd.concat(df)
soup = bs4(response.text, 'html.parser')

df.rename(
    columns={'Link': "Offender Information", "Link.1": "Last Statement URL"},
    inplace=True,
)

# Use bs4 to get the Offender Information URLs
offender_information_urls = []
# Select the correct <a href> tag based on second tag I guess
for link in soup.select('tr>td:nth-child(2)>a'):
    offender_information_urls.append(f"{base_url}/" + link['href'])
# Add the URLs to the dataframe
df["Offender Information"] = offender_information_urls

# Use bs4 to get the Last Statement URLs
last_statement_urls = []
# Select the correct <a href> tag based on third tag I guess
for link in soup.select('tr>td:nth-child(3)>a'):
    last_statement_urls.append(f"{base_url}/" + link['href'])
# Add the URLs to the dataframe
df["Last Statement URL"] = last_statement_urls

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
# We'll first create a list of keywords indicating no last statement
# https://stackoverflow.com/a/43399866
keywords = ['This inmate declined to make a last statement.','No statement was made.','No statement given.','None','None.','None ','(Written statement)','Spoken: No','Spoken: No.','No','No last statement.','No, I have no final statement.', '']
empty_statements = df[df['Last Statement'].isin(keywords)].Execution.count() + df['Last Statement'].isnull().sum().sum()
# Drop all rows containing these "no last statement" keywords
df = df[~df['Last Statement'].isin(keywords)]
# Now we drop all rows containing NaN
# https://hackersandslackers.com/pandas-dataframe-drop/
df.dropna(axis=0,how='any',subset=['Last Statement'],inplace=True)
print(f"Removed {empty_statements} rows with no last statement...")
print(f"{len(df.index)} rows remain.")

# Reindex the dataframe so the rows are sequential again
df.reset_index(drop=True, inplace=True)

# Re-sort the dataframe index
# This is to prevent KeyErrors when slicing the dataframe via loc[x:y] (i.e, the worklist variable)
# https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_index.html
# https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#slicing-with-labels
df.sort_index(axis=0,inplace=True)

# Sort the df by oldest executions first
# https://stackoverflow.com/a/67689015
# https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html
print("Sorting dataframe by oldest execution first...")
df.sort_values(by="Date", key=pd.to_datetime, ascending=True, inplace=True)

# Export the df to a CSV for debugging
# Use utf-8-sig encoding
# https://stackoverflow.com/a/43684587
df.to_csv("/mnt/c/Temp/offenders_data_utf8.csv", encoding="utf-8-sig")

# Calculate some interesting statistics
# Create a function to find percentages
# https://www.skillsugar.com/how-to-calculate-a-percentage-in-python
def percentage(first, second, integer = False):
    percent = first / second * 100
    if integer:
        return int(percent)
    return percent

print("Calculating statistics...")
oldest_inmate = df.loc[df.Age.idxmax()] # use idxmax to find the index of the oldest age, then use loc to find that whole entry
youngest_inmate = df.loc[df.Age.idxmin()] # https://moonbooks.org/Articles/How-to-find-a-minimum-value-in-a-pandas-dataframe-column-/
average_age = int(df.Age.mean()) # https://stackoverflow.com/a/3398439
jesus_statements = len(df[df['Last Statement'].str.contains("Jesus|Christ")]) # https://stackoverflow.com/a/31583241
jesus_statements_percentage = f"{round(int(float(percentage(jesus_statements, len(df.index)))), 1)}" + "%" # Round to 0 decimal places. Also convert to float then int to prevent Str errors
allah_statements = len(df[df['Last Statement'].str.contains("Allah")])
allah_statements_percentage = f"{round(int(float(percentage(allah_statements, len(df.index)))), 1)}" + "%"
yahweh_statements = len(df[df['Last Statement'].str.contains("Yahweh|Yahwe|Yahve|Yahuwah")])
yahweh_statements_percentage = f"{round(int(float(percentage(yahweh_statements, len(df.index)))), 1)}" + "%"

# Age distribution
# https://riptutorial.com/pandas/example/5965/grouping-numbers
age_groups = pd.cut(df.Age, bins=[18, 20, 29, 39, 49, 59, 69, 79, 89], labels=['18 to 20 years old', '21 to 29 years old', '30 to 39 years old', '40 to 49 years old', '50 to 59 years old', '60 to 69 years old', '70 to 79 years old', '80 to 89 years old'])
# Plot the groups
# https://stackoverflow.com/a/40314011
age_groups_count = df.groupby(age_groups)['Age'].count()
age_plot = age_groups_count.plot(kind='bar', title='Age Distribution of Executed Inmates in Texas, 1982-2021', ylabel='Number of Inmates', xlabel='Age Group')
# Annotate the bars
# https://stackoverflow.com/a/67561982
age_plot.bar_label(age_plot.containers[0], label_type='edge')
# Save the plot as a PNG
print("Saving the plotted age graph...")
plt.savefig("/tmp/age_distribution.png", bbox_inches = 'tight')
# Close the figure window to prevent the next graph from using the same values
# https://stackoverflow.com/a/8228808
plt.clf()

# Racial distribution
race_count = df.groupby('Race')['Execution'].count()
race_plot = race_count.plot(kind='bar', title='Racial Distribution of Executed Inmates in Texas, 1982-2021', ylabel='Number of Inmates', xlabel='Race')
race_plot.bar_label(race_plot.containers[0], label_type='edge')
# Save the plot as a PNG
print("Saving the plotted race graph...")
plt.savefig("/tmp/racial_distribution.png", bbox_inches = 'tight')
# Close the figure window to prevent the next graph from using the same values
# https://stackoverflow.com/a/8228808
plt.clf()

print(f"{len(df.index)} total last statements.")
print(f"{empty_statements} inmates declined to give a last statement.")
print(f"Christianity: {jesus_statements} inmates ({jesus_statements_percentage}) mentioned Jesus Christ at least once in their last statement.")
print(f"Islam: {allah_statements} inmates ({allah_statements_percentage}) mentioned Allah at least once in their last statement.")
print(f"Judaism: {yahweh_statements} inmates ({yahweh_statements_percentage}) mentioned Yahweh at least once in their last statement.")
print(f"The oldest executed inmate was {oldest_inmate['First Name']} {oldest_inmate['Last Name']} at {oldest_inmate.Age} years old.")
print(f"The youngest executed inmate was {youngest_inmate['First Name']} {youngest_inmate['Last Name']} at {youngest_inmate.Age} years old.")
print(f"The average age at execution was {average_age} years old.")

# Create a post with the statistics and plots
# Upload the PNGs to Imgur and get the resulting link
print("Uploading graphs to Imgur...")
age_distribution_link = imgur_client.upload_from_path('/tmp/age_distribution.png', anon=False)['link']
racial_distribution_link = imgur_client.upload_from_path('/tmp/racial_distribution.png', anon=False)['link']

# Set up the body
# https://www.techbeamers.com/python-multiline-string/
body = f"""<ul> 
    <li>{empty_statements} inmates declined to give a last statement.</li>
    <li>{len(df.index)} total last statements.</li>
    <li>Christianity: {jesus_statements} inmates ({jesus_statements_percentage}) mentioned Jesus Christ at least once in their last statement.</li>
    <li>Islam: {allah_statements} inmates ({allah_statements_percentage}) mentioned Allah at least once in their last statement.</li>
    <li>Judaism: {yahweh_statements} inmates ({yahweh_statements_percentage}) mentioned Yahweh at least once in their last statement.</li>
    <li>The oldest executed inmate was {oldest_inmate['First Name']} {oldest_inmate['Last Name']} at {oldest_inmate.Age} years old.</li>
    <li>The youngest executed inmate was {youngest_inmate['First Name']} {youngest_inmate['Last Name']} at {youngest_inmate.Age} years old.</li>
    <li>The average age at execution was {average_age} years old.</li>
</ul><br></br><h1>Age Distribution of Executed Inmates</h1><img src="{age_distribution_link}" alt="Age Distribution of Executed Inmates, Texas 1982-2021"><br></br><h1>Racial Distribution of Executed Inmates</h1><img src="{racial_distribution_link}" alt="Racial Distribution of Executed Inmates, Texas 1982-2021">"""
tumblr_client.create_text('goodbyewarden', state="published", slug="statistics", title="Some Interesting Statistics", body=body)

# Iterate over each inmate in the dataframe and use .loc to select specific rows
# https://towardsdatascience.com/how-to-use-loc-and-iloc-for-selecting-data-in-pandas-bd09cb4c3d79
# Also, we're gonna hit Tumblr's API limits as it stands: 
#    1. Can only post 250 posts/day to either the queue or published
#    2. Can only have 300 posts in the queue at once.
# Algebra comes in handy here. My high school math teacher has finally been vindicated 15 years later 👏
# It doesn't matter how many rows we have: we need to post x posts until we remain with 300 posts
# The last 300 posts will be queued
# Use SymPy to solve an algebraic equation
# https://scipy-lectures.org/packages/sympy.html#equation-solving
x = Symbol('x')
# Solve for x: how many posts do we need to immediately publish?
posts_to_publish = int(solve(len(df.index)-300-x, x)[0])
# Now we have the dataframe we need to publish immediately
df_posts_to_publish = df.loc[df.first_valid_index():(df.first_valid_index() - posts_to_publish)]
# Use Numpy to split the dataframe into sections of roughly 100
df_posts_to_publish_sections = np.array_split(df_posts_to_publish, (len(df_posts_to_publish) / 100), axis=0)
for inmate in df_posts_to_publish_sections[0].itertuples(): # the iterate over the first batch
    # Generate the last statement for each inmate
    quote = inmate[11]
    # Generate the rest of the "source" information
    # use an f-string to assign output to the 'source' variable
    # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
    # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
    source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
    # Generate the tags 
    tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
    # Send the API call (the post will be queued) 
    print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
    tumblr_client.create_quote('goodbyewarden', state="published", quote=quote, source=source, tags=tags) 
# Wait 24 hours after each batch
print("Sleeping for 24 hours...")    
time.sleep(86400)

try: # Handle the exception using a try/except block if the section doesn't exist https://stackoverflow.com/a/11902480
    gotdata = df_posts_to_publish_sections[1]
    for inmate in df_posts_to_publish_sections[1].itertuples(): # the iterate over the second batch
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
        # Send the API call (the post will be queued) 
        print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        tumblr_client.create_quote('goodbyewarden', state="published", quote=quote, source=source, tags=tags) 
    # Wait 24 hours after each batch
    print("Sleeping for 24 hours...")    
    time.sleep(86400)    
except IndexError:
    gotdata = 'null' 
    
try:
    gotdata2 = df_posts_to_publish_sections[2]
    for inmate in df_posts_to_publish_sections[2].itertuples(): # the iterate over the third batch
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
        # Send the API call (the post will be queued) 
        print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        tumblr_client.create_quote('goodbyewarden', state="published", quote=quote, source=source, tags=tags) 
    # Wait 24 hours after each batch
    print("Sleeping for 24 hours...")    
    time.sleep(86400)
except IndexError:
    gotdata2 = 'null' 

try:
    gotdata3 = df_posts_to_publish_sections[3]  
    for inmate in df_posts_to_publish_sections[3].itertuples(): # the iterate over the third batch
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
        # Send the API call (the post will be queued) 
        print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        tumblr_client.create_quote('goodbyewarden', state="published", quote=quote, source=source, tags=tags) 
    # Wait 24 hours after each batch
    print("Sleeping for 24 hours...")    
    time.sleep(86400)
except IndexError:
    gotdata3 = 'null'
    
try:
    gotdata4 = df_posts_to_publish_sections[4]  
    for inmate in df_posts_to_publish_sections[4].itertuples(): # the iterate over the third batch
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
        # Send the API call (the post will be queued) 
        print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        tumblr_client.create_quote('goodbyewarden', state="published", quote=quote, source=source, tags=tags) 
    # Wait 24 hours after each batch
    print("Sleeping for 24 hours...")    
    time.sleep(86400)
except IndexError:
    gotdata4 = 'null'
    
try:
    gotdata5 = df_posts_to_publish_sections[5]  
    for inmate in df_posts_to_publish_sections[5].itertuples(): # the iterate over the third batch
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
        # Send the API call (the post will be queued) 
        print(f"Posting the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        tumblr_client.create_quote('goodbyewarden', state="published", quote=quote, source=source, tags=tags) 
    # Wait 24 hours after each batch
    print("Sleeping for 24 hours...")    
    time.sleep(86400)
except IndexError:
    gotdata5 = 'null' 

# Queue the remaining posts
# Because the dataframe's index is reversed, the queue should start at the end of the "publish immediately" dataframe MINUS one
# i.e if the post df ended at 277, the queue df should start at 276 and then continue to 0 (the last valid index)
posts_to_queue = df_posts_to_publish.last_valid_index() - 1
if (len(df.loc[posts_to_queue:df.last_valid_index()])) <= 300: # we're expecting <300 posts, so add an if check
    for inmate in df.loc[posts_to_queue:df.last_valid_index()].itertuples():
        # Generate the last statement for each inmate
        quote = inmate[11]
        # Generate the rest of the "source" information
        # use an f-string to assign output to the 'source' variable
        # https://www.reddit.com/r/learnpython/comments/pxtzov/how_to_assign_an_output_a_variable/hepor21/
        # (For Tumblr) HTML formatting guidelines: https://github.com/tumblr/pytumblr#creating-a-quote-post
        source = f"{inmate[5]} {inmate[4]}. {inmate.Age} years old. Executed {inmate.Date}. <br></br> <small> <a href='{inmate[2]}'>Offender Information</a> <br></br> <a href='{inmate[3]}'>Last Statement</a> </small>"
        # Generate the tags 
        tags = [f"{inmate[5]} {inmate[4]}, Execution #{inmate.Execution}, Index {inmate.Index}"]
        # Send the API call (the post will be queued)  
        print(f"Queueing the last statement for {inmate[5]} {inmate[4]}. Index {inmate.Index}")
        tumblr_client.create_quote('goodbyewarden', state="queue", quote=quote, source=source, tags=tags) 
else:
    print("The number of expected posts was NOT less than 300. No API call will be sent.")