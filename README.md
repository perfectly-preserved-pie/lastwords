
# Last Words

A Python script that posts the last words of each inmate on Texas's death row right before they were executed to my website, https://lastwords.fyi. Links to the full offender information & original last statement are included with each post.


## Acknowledgements

 - StackOverflow
 - [/r/learnpython](https://www.reddit.com/r/learnpython)
 - [How to write a Good readme](https://bulldogjob.com/news/449-how-to-write-a-good-readme-for-your-github-project)
 - [The easiest way to create a README](https://readme.so/)


## What does this do?

- Gets the offender's name, age, race, and last statement
- Runs basic statistics on the above information, including generating plots
- Removes any inmates with no last statement
- Posts as many statements as possible to https://lastwords.fyi  without hitting the Tumblr API limits and queues the rest


## Installation

Simply download lastwords.py and run it with Python 3. 

```bash
  python3 lastwords.py
```
    
## Lessons Learned

This was my very first Python project 👶 Check out [my blog post](https://automateordie.io/Last-Words-Project/) where I write about the whole process!

