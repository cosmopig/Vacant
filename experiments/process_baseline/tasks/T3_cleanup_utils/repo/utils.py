import os, sys, json, re
def ReadCfg(p):
  f=open(p);d=json.load(f);f.close();return d
def slug(s):
    s=s.lower()
    s=re.sub('[^a-z0-9]+','-',s)
    return s.strip('-')
def slug2(s):  # old version, still used?
    return s.lower().replace(' ','-')
def chunks(l,n):
    out=[]
    i=0
    while i<len(l):
        out.append(l[i:i+n]); i=i+n
    return out
def unused_helper(x):
    return x*2
