#!/usr/bin/python3

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

import time

today = int(time.time())

class epmc:
    def __init__(self):
        self.useragent = "epmc.py"
        self.limit      = 200
        
    def search(self, q):
        ''' search via the API'''
        qe = q# urlencode(str(q), quote_via=quote_plus)
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={Q}&format=json".format(Q=qe)
        res = requests.get(url =url)
        return(res.json())

    def references(self, id, cl = "MED"):
        ''' fetch the references of the given publication'''
        u = "https://www.ebi.ac.uk/europepmc/webservices/rest/{CL}/{ID}/references?page=1&pageSize={S}&format=json"
        url = u.format(CL=cl, ID= id, S = self.limit )
        res = requests.get(url = url)
        return(res.json())

    def citations(self, id, cl = "MED"):
        '''fetch al pubilcations that cited this one'''
        return()

class epmcBuffer:
    '''this class is to be used instead of th pure
    epmc class. Here request performed previsously
    will be cached in a database and only be requested again 
    if a certain, user defined, number of days has passed'''
    def __init__(self):
        self.epmc = epmc()
        self.daylimit = 5
        self.DB()
    
    def DB(self, dbname = ".epmc.db"):
        # connect to the sqlite db
        self.db  = sqlite3.connect(dbname)
        self.c   = self.db.cursor()
        # create all tables that we need
        self.createTable()
        
    
    def createTable(self):
        # a single table to hold the information
 
        self.c.execute('''CREATE TABLE IF NOT EXISTS paper 
                          (id text , source text,  title text, author TEXT, year INT, refRet INT DEFAULT 999999999999999, citRet INT DEFAULT 999999999999999 )''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS `edges` 
                          ( `FROM` text, `FSOURCE` text,  `TO`  text, `TSOURCE` text )''')
        self.db.commit()

    def savePaper(self, res):
        # check if paper exists already:
        self.c.execute('SELECT * FROM `paper` WHERE id=? AND source=?', (res['id'], res['source']))
        r = self.c.fetchone()
        if r == None:
            self.c.execute('INSERT INTO `paper` (id, source, title, author, year)\
                           VALUES (?, ?, ?, ?, ?)', (res['id'], res['source'], res['title'], res['authorString'], res['pubYear']))
    def references(self, id, source = "MED"):
        '''fetch and return a list of reference ids'''
        # check if id class combi is in databank
        self.c.execute('SELECT * FROM `paper` WHERE id=? AND source=?', (id, source))
        r = self.c.fetchone()
        fetchFromWeb = True
        if r != None:
            fetchFromWeb = False
            # we already have the paper in the DB
            # check if its to old
            if r[5] - today > (self.daylimit * 60 * 60 * 24): # the magic number 6 is the field number fo refRet
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
            res = self.epmc.references(id, source)

            self.c.execute("UPDATE `paper` SET refRet=? WHERE id=? AND source=?", (today, id, source))
            # save the result in the database if interesting:
            if res['hitCount'] > 0:
                for reference in res['referenceList']['reference']:
                    # save metadata of this it if not already
                    # update then the refRet field
                    if 'id' in reference.keys():
                        self.c.execute('INSERT INTO `edges` (`FROM`, `FSOURCE`,  `TO`,  `TSOURCE` )  VALUES (?, ?, ?,?)', (id, source, reference['id'], reference['source'] ))
                        self.savePaper(reference)
        self.db.commit()

        # fetch the data we want from the db
        # this is more simple than maintaining the data over the scope
        # it is also slower
        refresults = self.c.execute("SELECT * FROM `edges` WHERE `FROM`=? AND `FSOURCE`=?",(id, source))
        print("checked ", id, fetchFromWeb)
        return(refresults.fetchall())
        




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

    parser.add_argument("-v", "--verbose", type = bool, 
                            help="increase output verbosity", default = False)
    args = parser.parse_args()

    # start a new DB server
    e = epmcBuffer()
    # now make hops:
    i = 0
    toVisit = [(args.id, args.source)]
    visited = []
    edges = []
    while i < args.count:
        for v in toVisit:
            if v in visited:
                continue
            newedges = e.references(v[0], v[1])
            for edge in newedges:
                p = (edge[2], edge[3])
                if p not in visited:
                    toVisit.append(p)
            edges.extend(newedges)
        i = i + 1
        print(i)
    # now that we have the data we can build a graph if we want
    g = Graph()

    # get all vertices

    '''
    # make vertices
    for key in db.vertices :
        g.add_vertex(key, label = db.vertices[key] )

    # get the edges:
    g.add_edges(db.edges) 
    summary(g)

    # combine by weight
    g.es["weight"] = 1
    g.simplify(combine_edges={"weight": "sum"})
    #layout = g.layout("kk")
    #plot(g, layout = layout)



    g.save(args.output + ".graphml", format="graphml")


    db.c.close()
    '''

main()
