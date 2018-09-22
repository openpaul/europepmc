# Simple europepmc.org graph 

This script is a simple API client for the europepmc database ([europepmc.org](europepmc.org)).
It takes an ID of an paper of interest (POI) and creates either a citation or a reference graph in both the graphml and gdf format.

This might be helpful for people doing literature research.

## The two output files
Both formats can be visualized using gephi ([gephi.org](https://gephi.org/)), but only files in the gdf format can be merged into the same workspace due to an ID problem (The IDs in the graphml format are created by iGraph and thus they do not relate to the papers id, resulting in wrong merges using gephi).

Attentions: The graphml format is written by igraph and the gdf format is written by a custom 
function written by me. So the graphml format should always be used, only if you want to load 
multiple graphs use the gdf.


## Run it

```
git clone https://github.com/openpaul/europepmc
python3 main.py -h
```

You'll need to input an id of the paper. So if you found the paper you like on the 
webpage ([europepmc.org](europepmc.org)) you can extract the info you need from the URI:

```
#https://europepmc.org/abstract/PMC/PMC6132391
cd europepmc
python3 main.py PMC6132391 PMC myfancygraphfile
```

### Example
If for example you are interested to see where a finding comes from and how it influenzed other research you could run the following steps.

```
# look in the history of a paper
python3 main.py 17166259 MED example/example_history 
# look into the researched fostered by the paper
python3 main.py 17166259 MED example/example_future -f 1 # the one can be any value, this is a bug and should be addressed
```

The load both files into gephi and color them differently to create a graph like this one:

![An example graph showing a result produced by using this scripts output in gephi](examples/example.png?raw=true)

In red are papers that were published citing the POI (white) and in blue are papers cited by this paper. Using gephi one can now explore the papers and find papers belonging to certain hubs or subnetworks.

Creating graphs using several papers of a field might help find papers that one might have overlooked otherwise.

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

So if you feel like fixing some bugs or improving speed or even just the style, please 
do not be afraid of doing some pull requests. I'll probably approve. 

Or just fork it and do as you please.


