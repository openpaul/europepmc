#!/usr/bin/python3

import colorsys
import argparse
import json
import requests
from urllib.parse import urlencode, quote_plus
import pprint
import codecs
import itertools
from igraph import *
import sqlite3
from time import sleep
import os, pickle    
import sys
import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

today = int(time.time())


def etAl(s, d = None):
    '''format a name string to et al ciation'''
    n = ""
    if s.count(",") > 1:
        # many authors, cant show all
        n = s.split(",")[0].split(" ")[0]
        n = "{} et al.".format(n)
    elif s.count(",") == 1:
        # two authors, show both
        m = s.split(",")
        ns = []
        for i in m:
            ns.append(i.strip().split(" ")[0])
        n = "{} and {}".format(ns[0],ns[1])
    else:
        # one author
        n = s.split(" ")[0]
    if d != None:
        n = "{} ({})".format(n, d)
    return(n)

class epmc:
    def __init__(self):
        self.useragent = "epmc.py"
        self.limit      = 10
        
    def search(self, q):
        ''' search via the API'''
        qe = q# urlencode(str(q), quote_via=quote_plus)
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={Q}&format=json".format(Q=qe)
        res = requests.get(url =url)
        return(res.json())

    def references(self, id, cl = "MED"):
        ''' fetch the references of the given publication'''
        u = "https://www.ebi.ac.uk/europepmc/webservices/rest/{CL}/{ID}/references?pageSize={S}&format=json"
        urlstring = u.format(CL=cl, ID= id, S = self.limit )
        result = requests.get(url = urlstring).json()
        
        # if hit count > self.limit,we need a paged loop
        if result["hitCount"] > self.limit:
            page = 1
            while len(result["referenceList"]["reference"]) < result["hitCount"]:
                page = page + 1
                newurl = "{}&page={}".format(urlstring, page)
                tmpres = requests.get(url  = newurl).json()
                result["referenceList"]["reference"].extend(tmpres["referenceList"]["reference"])
        return(result)
        

    def citations(self, id, cl = "MED"):
        '''fetch al pubilcations that cited this one'''
        urlstring = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/{}/citations?pageSize={}&format=json".format(cl, id, self.limit)
        result = requests.get(url  = urlstring).json()
        
        # if hit count > self.limit,we need a paged loop
        if result["hitCount"] > self.limit:
            page = 1
            while len(result["citationList"]["citation"]) < result["hitCount"]:
                page = page + 1
                newurl = "{}&page={}".format(urlstring, page)
                tmpres = requests.get(url  = newurl).json()
                result["citationList"]["citation"].extend(tmpres["citationList"]["citation"])
                
        return(result)

class epmcBuffer:
    '''this class is to be used instead of th pure
    epmc class. Here request performed previsously
    will be cached in a database and only be requested again 
    if a certain, user defined, number of days has passed'''
    def __init__(self,dbname = ".epmc.db", verbose = False):
        self.epmc = epmc()
        self.daylimit = 5 # number of days we trust the number of citations did not change
        self.reflimit = 60 # number of days we trust the number of references did not change
        self.verbose = verbose
        self.DB(dbname)
    
    def DB(self, dbname = ".epmc.db"):
        # connect to the sqlite db
        self.db  = sqlite3.connect(dbname)
        self.c   = self.db.cursor()
        # create all tables that we need
        self.createTable()
        
    def updateCitationCount(self, items ):
        '''for each paper update the citation count for future reference'''
        sql = "SELECT id, source, citRet FROM paper"
        res = self.c.execute(sql).fetchall()
        # remove all items that are not in the item list
        # this should be better than creating an awefull complex sql string
        # make a id-source list:
        idsList = []
        for i in items:
            idsList.append("-".join(i))
        i = 0
        resF = []
        for r in res:
            if "-".join(r[0:2]) in idsList:
                resF.append(r)
            i = i + 1
        total = len(resF)
        del res
        print("Checking citations of {} papers".format(len(resF)))
        i = 0
        j = 0
        for r in resF:
            if today - r[2] > (60*60* 24 * self.daylimit):
                # fetch new from the interweb:
                cits = self.citations(r[0], r[1])
                #ncits = cits['hitCount']
                #self.c.execute("UPDATE `paper` SET citedBy=?, citRet=? WHERE id=? AND source=?", (ncits, today, r[0], r[1]))
                i = i + 1
                if i % 100 == 0:
                    self.db.commit()
                    #stats:
                #    percentagedone = round(100* j/total, 1)
                #    print("{}% done ({}/{}) (intermediate saving)".format(percentagedone, j, total))
            if round((100 * j/total),1) % 1 ==  0 or True:
                percentagedone = round(100* j/total, 1)
                s  =("{}% done ({}/{})".format(percentagedone, j, total))
                sys.stdout.write('\r')
                # the exact output you're looking for:
                sys.stdout.write(s)
                sys.stdout.flush()
            j = j + 1
        self.db.commit()


    def createTable(self):
        # a single table to hold the information
 
        self.c.execute('''CREATE TABLE IF NOT EXISTS paper 
                          (id text , source text,  title text, author TEXT, year INT,citedBy INT DEFAULT 0, refRet INT DEFAULT 0, citRet INT DEFAULT 0 )''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS `edges` 
                          ( `FROM` text, `FSOURCE` text,  `TO`  text, `TSOURCE` text )''')
        self.db.commit()

    def savePaper(self, res):
        # check if paper exists already:
        self.c.execute('SELECT * FROM `paper` WHERE id=? AND source=?', (res['id'], res['source']))
        r = self.c.fetchone()
        if r == None:
            if set(['id','source','title','authorString','pubYear']).issubset(res.keys()):
                self.c.execute('INSERT INTO `paper` (id, source, title, author, year)\
                           VALUES (?, ?, ?, ?, ?)', (res['id'], res['source'], res['title'], res['authorString'], res['pubYear']))
                self.db.commit()


    def references(self, id, source = "MED", verbose = False):
        '''fetch and return a list of reference ids'''
        # check if id class combi is in databank
        self.c.execute('SELECT * FROM `paper` WHERE id=? AND source=?', (id, source))
        r = self.c.fetchone()
        fetchFromWeb = True
        if r != None:
            fetchFromWeb = False
            # we already have the paper in the DB
            # check if its to old
            if today - r[6] > (self.reflimit * 60 * 60 * 24): # the magic number 6 is the field number fo refRet
                # delete this entry and fetch new
                self.c.execute('DELETE FROM `edges` WHERE `FROM` = ? AND `FSOURCE`= ? ',
                        (id, source))
                fetchFromWeb = True

        else:
            # need to insert this paper into the DB
            possres = self.epmc.search(id)
            # save all the results in the database, as there is no reason to discard them here
            if possres['hitCount'] > 0:
                for res in possres['resultList']['result']:
                    if 'id' in res.keys():
                        self.savePaper(res)
        
        # here make a call to the original class to query the server
        if fetchFromWeb:
            if self.verbose:
                print("need to fetch {} from web".format(id))
            res = self.epmc.references(id, source)

            self.c.execute("UPDATE `paper` SET refRet=? WHERE id=? AND source=?", (today, id, source))
            # save the result in the database if interesting:
            if res['hitCount'] > 0:
                for reference in res['referenceList']['reference']:
                    # save metadata of this it if not already
                    # update then the refRet field
                    if 'id' in reference.keys() and 'source' in reference.keys():
                        self.c.execute('INSERT INTO `edges` (`FROM`, `FSOURCE`,  `TO`,  `TSOURCE` )  VALUES (?, ?, ?,?)', (id, source, reference['id'], reference['source'] ))
                        self.savePaper(reference)
        self.db.commit()

        # fetch the data we want from the db
        # this is more simple than maintaining the data over the scope
        # it is also slower
        refresults = self.c.execute("SELECT * FROM `edges` WHERE `FROM`=? AND `FSOURCE`=?",(id, source))
        if fetchFromWeb and self.verbose:
            print("checked ", id, fetchFromWeb)
        return(refresults.fetchall())

    def citations(self, id, source = "MED"):
        '''fetch and return a list of reference ids'''
        # check if id class combi is in databank
        self.c.execute('SELECT citRet FROM `paper` WHERE id=? AND source=?', (id, source))
        r = self.c.fetchone()
        fetchFromWeb = True
        if r != None:
            fetchFromWeb = False
            # we already have the paper in the DB
            # check if its to old
            if today - r[0] > (self.reflimit * 60 * 60 * 24): # the magic number 6 is the field number fo refRet
                # delete this entry and fetch new
                self.c.execute('DELETE FROM `edges` WHERE `TO` = ? AND `TSOURCE`= ? ',
                        (id, source))
                fetchFromWeb = True

        else:
            # need to insert this paper into the DB
            possres = self.epmc.search(id)
            # save all the results in the database, as there is no reason to discard them here
            if possres['hitCount'] > 0:
                for res in possres['resultList']['result']:
                    if 'id' in res.keys():
                        self.savePaper(res)
        
        # here make a call to the original class to query the server
        if fetchFromWeb:
            if self.verbose:
                print("need to fetch ciatations of {} from web".format(id))
            res = self.epmc.citations(id, source)

            citedBy = res["hitCount"]
            self.c.execute("UPDATE `paper` SET citRet=?,citedBy=? WHERE id=? AND source=?", (today, citedBy, id, source))
            # save the result in the database if interesting:
            if res['hitCount'] > 0:
                for reference in res['citationList']['citation']:
                    # save metadata of this it if not already
                    # update then the refRet field
                    if 'id' in reference.keys() and 'source' in reference.keys():
                        self.c.execute('INSERT INTO `edges` (`FROM`, `FSOURCE`,  `TO`,  `TSOURCE` )  VALUES (?, ?, ?,?)', (reference['id'], reference['source'], id, source ))
                        self.savePaper(reference)
        self.db.commit()

        # fetch the data we want from the db
        # this is more simple than maintaining the data over the scope
        # it is also slower
        refresults = self.c.execute("SELECT * FROM `edges` WHERE `TO`=? AND `TSOURCE`=?",(id, source))
        if fetchFromWeb and self.verbose:
            print("fetched citations of {} ".format( id))
        return(refresults.fetchall())

    def nodes(self):
        '''return all nodes with citation values'''
        res = self.c.execute("SELECT id, source, citedBy, author, year, title FROM paper").fetchall()
        n = {}
        for r in res:
            n["{}_{}".format(r[0],r[1])] = {"name": etAl(r[3],r[4]), "cited": r[2],\
                                            "title": r[5]}

        return(n)




def get_N_HexCol(N=5):
    HSV_tuples = [(x * 1.0 / N, 0.5, 0.5) for x in range(N)]
    hex_out = []
    for rgb in HSV_tuples:
        rgb = map(lambda x: int(x * 255), colorsys.hsv_to_rgb(*rgb))
        hex_out.append('#%02x%02x%02x' % tuple(rgb))
    return hex_out

# from https://pythonprogramminglanguage.com/kmeans-elbow-method/
def clusterByTitle(g, k = 5):

    titles = []
    for v in g.vs:
        titles.append(v["title"])

    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(titles)
    model = KMeans(n_clusters=k, 
                   init='k-means++', max_iter=100, n_init=1)
    model.fit(X)

    # Get the class and assign color hexes to 
    # the graph vertices
    classes = model.predict(X)
    cols = get_N_HexCol(k)

    g.vs["color"] = ([cols[i] for i in classes ])
    g.vs["clusterK"] = classes

    order_centroids = model.cluster_centers_.argsort()[:, ::-1]
    terms = vectorizer.get_feature_names()
    for i in range(k):
        print("Cluster %d:" % i),
        for ind in order_centroids[i, :10]:
            print(' %s' % terms[ind]),


    return(g)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id" , type=str,
                            help="The ID of the paper")
    parser.add_argument("source" , type=str,default="MED",
                            help="source of the paper (MED)")

    parser.add_argument("output" , type=str,
                            help="output file")

    parser.add_argument("-c","--count" , type=int,
            help="number of hops, default: 2", default = 2)

    parser.add_argument("-d","--db" , type=str,
            help="Name of the db file", default = "cache.sqlite")

    parser.add_argument("-f", "--future", type = bool, 
                            help="instead of references use the citations and show how this publiction was recived", default = False)
    parser.add_argument("-t", "--trim", type = int,
            help = "Minimal Number of edges a nodes needs to be shown", default = 2)
    parser.add_argument("-z", "--cited", type = int,
            help = "Minimal Number of citations nodes needs to be shown", default = 2)

    parser.add_argument("-k", "--kmeans", type = int,
            help = "K for means clustering, 0 for deactivating", default = 10)
    parser.add_argument("-v", "--verbose", type = bool, 
                            help="increase output verbosity", default = False)
    args = parser.parse_args()

    # start a new DB server
    e = epmcBuffer(dbname = args.db, verbose = args.verbose)
    # now make hops:
    i = 0
    toVisit = [(args.id, args.source)]
    edges = []
    j = 0
    while i < args.count:
        j = 0
        k = len(toVisit)
        while j < k:
            v = toVisit[j]
            j = j+1
            if args.future:
                newedges = e.citations(v[0], v[1])
            else:
                if args.verbose:
                    print("fetching references now")
                newedges = e.references(v[0], v[1])
            for edge in newedges:
                if args.future:
                    p = (edge[0], edge[1])
                else:
                    p = (edge[2], edge[3])
                toVisit.append(p)
            edges.extend(newedges)
        i = i + 1
        print(i)
    print("Database done, will now update citation counts for all papers")
    e.updateCitationCount( items = list(set(toVisit)))
    # now that we have the data we can build a graph if we want
    g = Graph()

    nodes = e.nodes()

    # for each node, we need to cound the number of related edges
    for key in nodes:
        nodes[key]["edges"] = 0
    
    for i in edges:
        s = "{}_{}".format(i[0], i[1])
        t = "{}_{}".format(i[2], i[3])
        nodes[s]["edges"] = nodes[s]["edges"] + 1

    # get all vertices
    for key in nodes:
        if nodes[key]["edges"] >= args.trim and nodes[key]["cited"] >= args.cited:
            g.add_vertex(key, label = nodes[key]["name"], size = nodes[key]["cited"],\
                    title = nodes[key]["title"])
    
    
    for i in edges:
        s = "{}_{}".format(i[0], i[1])
        t = "{}_{}".format(i[2], i[3])
        if nodes[s]["edges"] >= args.trim and nodes[t]["edges"] >= args.trim \
           and nodes[s]["cited"] >= args.cited and nodes[t]["cited"] >= args.cited:
            g.add_edge(s,t)

    g.simplify()
    if args.kmeans > 0:
        if args.verbose:
            print("dooing Kmeans clustering on titles")
        g = clusterByTitle(g, args.kmeans)
        
    if args.verbose:
        summary(g)


    g.save(args.output + ".graphml", format="graphml")

    print(args.trim)

main()
