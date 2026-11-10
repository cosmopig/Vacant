from utils import ReadCfg, slug, slug2, chunks

def titles_to_paths(titles):
    return [slug(t) + ".md" for t in titles]

def legacy_paths(titles):
    return [slug2(t) for t in titles]

def batches(items):
    return chunks(items, 3)
