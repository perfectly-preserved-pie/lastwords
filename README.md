
# Last Words

A Python script that posts the last words of each inmate on [Texas's death row](https://www.tdcj.texas.gov/death_row/dr_executed_offenders.html) right before they were executed to my website, https://lastwords.fyi. Links to the full offender information & original last statement are included with each post.


## Acknowledgements

 - StackOverflow
 - [/r/learnpython](https://www.reddit.com/r/learnpython)
 - [Peeps in the #scripting and #python channels in the MacAdmins Slack](https://www.macadmins.org/)
 - [How to write a Good readme](https://bulldogjob.com/news/449-how-to-write-a-good-readme-for-your-github-project)
 - [The easiest way to create a README](https://readme.so/)


## What does this do?

- Gets the offender's name, age, race, and last statement
- Runs basic statistics on the above information, including generating plots
- Removes any inmates with no last statement
- Posts as many statements as possible to https://lastwords.fyi  without hitting the Tumblr API limits and queues the rest
    
## Lessons Learned

This was my very first Python project 👶 Check out [my blog post](https://automateordie.io/lastwords/) where I write about the whole process!

