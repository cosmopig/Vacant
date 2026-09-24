Create a word cloud from text after removing URLs and plot it.
The function should raise the exception for: ValueError("No words available to generate a word cloud after removing URLs."): If there are no words available to generate a word cloud after removing URLs.
The function should output with:
    WordCloud object: The generated word cloud.
You should write self-contained code starting with:
```
import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt
def task_func(text):
```