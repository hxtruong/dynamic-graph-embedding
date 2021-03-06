# -*- coding: utf-8 -*-
"""get_cit-hepth_data.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1FByO9Bke23iZfuQhQzr6lVP-jLeAIoxV

# CIT-HEPTH

Reference: 
    - http://networkrepository.com/ca-cit-HepTh.php

**Describe**: 
> Arxiv HEP-TH (high energy physics theory) citation graph is from arXiv and covers all the citations. Edges from u to v indicate that a paper u cited another paper v. If a paper cites, or is cited by, a paper outside the dataset, the graph does not contain any information about this. The data is of the papers in the period from January 1993 to April 2003.

# Library
"""

import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import requests
import zipfile
from datetime import datetime
import os

"""# Download"""

link_dts = 'http://nrvis.com/download/data/ca/ca-cit-HepTh.zip'
dts_zip = 'ca-cit-HepTh.zip'
dts_name = 'ca-cit-HepTh.edges'

r1 = requests.get(link_dts, allow_redirects=True)
open(dts_zip, 'wb').write(r1.content)

with zipfile.ZipFile(dts_zip, 'r') as zip_ref:
    zip_ref.extractall()

"""# Handle data"""

df = None
with open(dts_name, 'r') as fi:
    lines = fi.readlines() 
    print(lines[:6])
    lines = lines[4:]
    lines_ = [list(map(int, line.strip().split())) for line in lines ]
    print(lines_[:4])
    df = pd.DataFrame(data=lines_, columns=['node_1', 'node_2', 'weight', 'timestamp'])

print()
print(df.dtypes)

df.info()

df.describe()

"""We will drop `weight` column and which row has value `timestamp = 0`. We can not create a temporal network without getting time stamp"""

df.drop(columns='weight', inplace=True)

df = df[df.timestamp != 0]

df.describe()

"""# Creating dynamic graph
Divide timestamp to `k` bin means `k` graph. Afterthat, we have 1 dynamic graph with `k` snapshot (static graph)
"""

k = 6

timestamp_range = (df.timestamp.max() - df.timestamp.min() + 1)//k 
timestamp_range

graphs_df = []
print("Start time: ", datetime.fromtimestamp(df.timestamp.min()) )
for i in range(k):
    upper_time = df.timestamp.min() + timestamp_range*(i+1)
    print(f"[{i}|\tUpper_time= {datetime.fromtimestamp(upper_time)}\t |Row|= {len(df[df.timestamp<upper_time])}")
    if i == k-1:
        graph_df = df.copy()
    else:
        graph_df = df[df.timestamp<upper_time].copy()
    graphs_df.append(graph_df)

graphs = []
for i in range(k):
    g = nx.from_pandas_edgelist(graphs_df[i], "node_1", "node_2", create_using=nx.Graph())
    graphs.append(g)
    print(f"Graph {i+1}:\t|V|={g.number_of_nodes()}\t|E|={g.number_of_edges()}")

"""# Save dynamic graph"""

NUMBER_SAVE_GRAPH = 5

folder = "./data/cit_hepth"
if not os.path.exists(folder):
    os.makedirs(folder)

for i in range(min(NUMBER_SAVE_GRAPH, k)):
    nx.write_edgelist(graphs[i],f'{folder}/graph_{str(i//10)+str(i%10)}.edgelist',data=False)

