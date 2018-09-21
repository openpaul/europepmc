# Simple europepmc.org graph 

This script is a simple API client for the europepmc.org database.
It takes an ID of an paper of interest (POI) and creates either a citation or a reference graph in both the graphml and gdf format.

Both formats can be visualized using gephi[https://gephi.org/], but only file with the gdf format can be merged into the same workspace due to an ID problem.

This might be helpful for people dooing literature research.


## Run it

```
git clone THIS repro
python3 main.py -h
```

You'll need to input an id of the paper. So if you found the paper you like on the 
mentioned webpage you can extract the info you need from the URI:

```
#https://europepmc.org/abstract/PMC/PMC6132391
python3 main.py PMC6132391 PMC
```



### Options explained
Most options are self explanatory but some options are woth explaining:

- *--future* By default the script loads the refernces of a paper and then takes the refernces of these papers and thus goes back in time until the publication of fire. 
By setting this flag you can go into the future as it will look at the citations. This way you can find the latest publications related to yout POI
- *--count* How many hops of the graph should be done?
- *--trim* and *--cited* Both these options are used to reduce the graph to a usable minimum.
Paper that do not fullfill your requirements are kicked out. The paper that was used as a seeding 
point will always be shown though.
- *--kmeans* If you want it does a Kmeans clustering on the titles which can be used as color coding. Not very usefull, but maybe to you?

# Disclaimer

Obviously there might be bugs in the script and features missing. For example it would be great to filter 
papers based on the expected citations due to age. So show new papers with few citations but only old ones
that have quite some. 

So if you feel like fixing some bugs or improving speed or even just the style, pleas 
do not be afraid of doing some pull requests. I'll probably approve. 

Or just fork it and do as you please.


